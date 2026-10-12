"""Weekday defaults are calculated on read; explicit daily edits always win."""
from datetime import date, timedelta
from postgres_backend import connect, read_connection, read_batch


def as_date(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def current_rule(user_id, on=None):
    on = as_date(on or date.today()).isoformat()
    with read_connection() as conn:
        return conn.execute('''SELECT * FROM recurring_schedules WHERE user_id=?
            AND starts_on<=? AND (ends_on IS NULL OR ends_on>=?)
            ORDER BY starts_on DESC LIMIT 1''', (user_id, on, on)).fetchone()


def save_rule(user_id, group, starts_on):
    start = as_date(starts_on)
    if group not in (None, 'warehouse', 'local'):
        return False, 'Wybierz Magazyn, Lokal albo brak stałego grafiku.'
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT id FROM users WHERE id=? AND active=1', (user_id,)).fetchone():
            return False, 'Nie znaleziono aktywnego pracownika.'
        if group and not conn.execute('''SELECT 1 FROM user_work_groups ug
                JOIN work_groups g ON g.id=ug.group_id
                WHERE ug.user_id=? AND g.code=?''', (user_id, group)).fetchone():
            return False, 'Najpierw przypisz pracownikowi ten obszar pracy w ustawieniach konta.'
        # Keep past rules: changing a default must not rewrite earlier months.
        conn.execute('DELETE FROM recurring_schedules WHERE user_id=? AND starts_on>=?',
                     (user_id, start.isoformat()))
        conn.execute('''UPDATE recurring_schedules SET ends_on=? WHERE user_id=?
            AND starts_on<? AND (ends_on IS NULL OR ends_on>=?)''',
            ((start-timedelta(days=1)).isoformat(), user_id, start.isoformat(), start.isoformat()))
        if group:
            conn.execute('INSERT INTO recurring_schedules(user_id, starts_on, work_group) VALUES(?,?,?)',
                         (user_id, start.isoformat(), group))
    return True, 'Stały grafik zapisany. Ręczne zmiany poszczególnych dni pozostają zachowane.'


def mark_overrides(conn, user_ids, work_date):
    value = as_date(work_date).isoformat()
    conn.executemany('''INSERT INTO schedule_overrides(user_id, work_date) VALUES(?,?)
        ON CONFLICT(user_id, work_date) DO NOTHING''', [(uid, value) for uid in user_ids])


def merge_defaults(rows, rules, blocked, first, last, user_ids=None, group=None):
    result = [dict(row) for row in rows]
    occupied = {(row['user_id'], row['work_date']) for row in result} | set(blocked)
    ids = None if user_ids is None else set(user_ids)
    for rule in rules:
        uid = rule['user_id']
        if (ids is not None and uid not in ids) or (group and rule['work_group'] != group):
            continue
        day = max(first, as_date(rule['starts_on']))
        end = min(last, as_date(rule['ends_on'])) if rule['ends_on'] else last
        while day <= end:
            key = (uid, day.isoformat())
            if day.weekday() < 5 and key not in occupied:
                result.append(dict(id=None, user_id=uid, work_date=key[1], start_time='',
                    end_time='', note='Stały grafik (pon.–pt.)', work_group=rule['work_group'],
                    created_at='', first_name=rule['first_name'], last_name=rule['last_name']))
                occupied.add(key)
            day += timedelta(days=1)
    return sorted(result, key=lambda row:(row['work_date'], row.get('last_name',''),
                                          row.get('first_name',''), row['user_id']))


def with_defaults(rows, first=None, last=None, user_ids=None, group=None):
    if user_ids is not None and not user_ids:
        return rows
    # Unbounded history tables display the next year; calendar views pass exact dates.
    first, last = as_date(first or date.today()), as_date(last or (date.today()+timedelta(days=365)))
    if last < first:
        return rows
    begin, end = first.isoformat(), last.isoformat()
    data = read_batch({
        'rules': ('''SELECT r.*, u.first_name, u.last_name FROM recurring_schedules r
            JOIN users u ON u.id=r.user_id WHERE u.active=1 AND r.starts_on<=?
            AND (r.ends_on IS NULL OR r.ends_on>=?)
            AND EXISTS (SELECT 1 FROM user_work_groups ug JOIN work_groups g ON g.id=ug.group_id
                        WHERE ug.user_id=r.user_id AND g.code=r.work_group)''', (end, begin)),
        'blocked': ('''SELECT user_id, work_date FROM schedule_overrides WHERE work_date BETWEEN ? AND ?
            UNION SELECT user_id, work_date FROM schedules WHERE work_date BETWEEN ? AND ?
            UNION SELECT user_id, availability_date AS work_date FROM availabilities
            WHERE availability_type='unavailable' AND availability_date BETWEEN ? AND ?''',
            (begin, end, begin, end, begin, end))
    })
    return merge_defaults(rows, data['rules'], {(r['user_id'],r['work_date']) for r in data['blocked']},
                          first, last, user_ids, group)
