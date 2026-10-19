"""Employee proposals never change the roster until an admin accepts them."""
import hashlib
import json
from datetime import date, datetime
from uuid import uuid4
from postgres_backend import connect, read_connection
from recurring import mark_overrides

ACCOUNT_HASHES = ('a1782b1a53e88ebb0b4ff023fb6a2d4a848bb92924bcdaa559802b369e9ed702', '5663515bdda2285d312c4bf09828ce696ea517476521177c36e6e03a4a9259da')


def members(conn):
    rows = conn.execute("SELECT id,first_name,last_name,email FROM users WHERE active=1 ORDER BY first_name").fetchall()
    return [r for r in rows if hashlib.sha256(r['email'].strip().lower().encode()).hexdigest() in ACCOUNT_HASHES]


def is_admin(conn, uid):
    return bool(conn.execute("SELECT 1 FROM users WHERE id=? AND active=1 AND access_level='admin'", (uid,)).fetchone())


def initialize_defaults(conn):
    # One-time setup of exactly the accounts requested by the owner.
    for person in members(conn):
        marker = f"proposal-access-20261019-{person['id']}"
        if conn.execute('SELECT 1 FROM app_migrations WHERE name=?', (marker,)).fetchone():
            continue
        group = conn.execute("SELECT id FROM work_groups WHERE code='local'").fetchone()
        if not group:
            continue
        conn.execute('INSERT OR IGNORE INTO user_work_groups(user_id,group_id) VALUES(?,?)', (person['id'], group[0]))
        if hashlib.sha256(person['email'].strip().lower().encode()).hexdigest() == ACCOUNT_HASHES[1]:
            # Do not overwrite an existing rule or historical daily exceptions.
            if not conn.execute('SELECT 1 FROM recurring_schedules WHERE user_id=?', (person['id'],)).fetchone():
                conn.execute("INSERT INTO recurring_schedules(user_id,starts_on,work_group) VALUES(?,?,'local')", (person['id'],date.today().isoformat()))
        conn.execute('INSERT INTO app_migrations(name,applied_at) VALUES(?,?)', (marker,datetime.now().isoformat()))


def snapshot(conn, uid, day):
    queries = [
        ('SELECT * FROM schedules WHERE user_id=? AND work_date=? ORDER BY id', (uid,day)),
        ('SELECT * FROM schedule_overrides WHERE user_id=? AND work_date=?', (uid,day)),
        ('SELECT * FROM recurring_schedules WHERE user_id=? AND starts_on<=? AND (ends_on IS NULL OR ends_on>=?) ORDER BY starts_on', (uid,day,day)),
        ('SELECT * FROM availabilities WHERE user_id=? AND availability_date=? ORDER BY id', (uid,day)),
    ]
    data = [[dict(r) for r in conn.execute(sql,args).fetchall()] for sql,args in queries]
    return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()


def context(actor):
    with read_connection() as conn:
        people = members(conn)
        if not is_admin(conn, actor) and actor not in {r['id'] for r in people}:
            return [], []
        rows = conn.execute('''SELECT p.*,u.first_name,u.last_name FROM schedule_proposals p
            JOIN users u ON u.id=p.author_id ORDER BY p.created_at DESC LIMIT 60''').fetchall()
        return people, rows


def submit(actor, day, assignments, note, token=None):
    day = date.fromisoformat(str(day))
    if day < date.today(): return False, 'Propozycja musi dotyczyć dzisiejszego lub przyszłego dnia.'
    clean = {int(k): v for k,v in assignments.items()}
    if not clean or any(v not in (None,'local') for v in clean.values()):
        return False, 'Wybierz Lokal albo wolne od grafiku.'
    if len(note) > 1000: return False, 'Opis może mieć maksymalnie 1000 znaków.'
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        allowed = {p['id'] for p in members(conn)}
        if actor not in allowed or not set(clean).issubset(allowed) or actor not in clean:
            return False, 'Brak uprawnienia do zaproponowania tej zmiany.'
        token = token or str(uuid4())
        if conn.execute('SELECT 1 FROM schedule_proposals WHERE id=?', (token,)).fetchone():
            return True, 'Propozycja jest już zapisana.'
        payload = json.dumps(clean,sort_keys=True)
        if conn.execute("SELECT 1 FROM schedule_proposals WHERE author_id=? AND work_date=? AND assignments=? AND status='pending'",(actor,day.isoformat(),payload)).fetchone():
            return True, 'Taka propozycja już czeka na decyzję szefa.'
        baseline = json.dumps({uid:snapshot(conn,uid,day.isoformat()) for uid in clean},sort_keys=True)
        conn.execute('''INSERT INTO schedule_proposals(id,author_id,work_date,assignments,baseline,note,status,created_at)
            VALUES(?,?,?,?,?,?,'pending',?)''',(token,actor,day.isoformat(),payload,baseline,note.strip(),datetime.now().isoformat()))
    return True, 'Propozycja wysłana do szefa. Obowiązujący grafik pozostaje bez zmian.'


def decide(actor, proposal_id, accept, reason=''):
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not is_admin(conn,actor): return False, 'Tylko szef może podjąć decyzję.'
        row = conn.execute('SELECT * FROM schedule_proposals WHERE id=?', (proposal_id,)).fetchone()
        if not row or row['status'] != 'pending': return False, 'Ta propozycja została już rozpatrzona.'
        changes = {int(k):v for k,v in json.loads(row['assignments']).items()}
        if accept:
            allowed = {p['id'] for p in members(conn)}
            if row['author_id'] not in allowed or not set(changes).issubset(allowed):
                return False, 'Konto uczestnika jest nieaktywne lub nie ma już uprawnień.'
            if row['work_date'] < date.today().isoformat(): return False, 'Termin minął. Odrzuć tę propozycję.'
            baseline = json.loads(row['baseline'])
            for uid,group in changes.items():
                if snapshot(conn,uid,row['work_date']) != baseline[str(uid)]:
                    return False, 'Grafik lub dostępność zmieniły się od zgłoszenia. Odrzuć propozycję i poproś o nową.'
                if group and conn.execute("SELECT 1 FROM availabilities WHERE user_id=? AND availability_date=? AND availability_type='unavailable'",(uid,row['work_date'])).fetchone():
                    return False, 'Pracownik zgłosił dzień wolny. Najpierw wyjaśnij dostępność.'
                if group and not conn.execute("SELECT 1 FROM user_work_groups ug JOIN work_groups g ON g.id=ug.group_id WHERE ug.user_id=? AND g.code='local'",(uid,)).fetchone():
                    return False, 'Pracownik nie jest przypisany do lokalu.'
            for uid,group in changes.items():
                mark_overrides(conn,[uid],row['work_date'])
                conn.execute("DELETE FROM schedules WHERE user_id=? AND work_date=? AND work_group IN ('local','warehouse')",(uid,row['work_date']))
                if group:
                    conn.execute("INSERT INTO schedules(user_id,work_date,start_time,end_time,note,work_group) VALUES(?,?,'','','Zaakceptowana propozycja','local')",(uid,row['work_date']))
        conn.execute('UPDATE schedule_proposals SET status=?,reviewer_id=?,reviewed_at=?,decision_note=? WHERE id=?',
            ('accepted' if accept else 'rejected',actor,datetime.now().isoformat(),reason.strip()[:1000],proposal_id))
    return True, 'Grafik zaktualizowany.' if accept else 'Propozycja odrzucona. Grafik nie został zmieniony.'
