"""Whole worked minutes, decimal money, weekly rounding only to grosz."""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP


def exact_amount(minutes,rate):
    return Decimal(int(minutes or 0))*Decimal(str(rate or 0))/Decimal(60)


def grosz(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)


def row_amount(row):
    row=dict(row)
    if row.get('payment_id') is not None:
        return Decimal(str(row.get('amount') or 0))
    return exact_amount(row.get('actual_minutes'),row.get('hourly_rate'))


def total_amount(rows):
    return grosz(sum((row_amount(row) for row in rows),Decimal(0)))


def total_due(rows):
    groups={}
    for row in rows:
        row=dict(row)
        groups.setdefault((row.get('user_id'),week_bounds(row['start_at'])[0]),[]).append(row)
    return sum((total_amount(group) for group in groups.values()),Decimal(0))


def shift_values(start,end,rate):
    a=datetime.strptime(start,'%Y-%m-%d %H:%M:%S')
    b=datetime.strptime(end,'%Y-%m-%d %H:%M:%S')
    minutes=max(0,int((b-a).total_seconds()//60))
    return minutes,minutes/60,float(exact_amount(minutes,rate))


def week_bounds(day):
    if isinstance(day,str): day=date.fromisoformat(day[:10])
    start=day-timedelta(days=day.weekday())
    return start,start+timedelta(days=6)


def weekly_breakdown(rows):
    weeks={}
    for source in rows:
        row=dict(source)
        if not row.get('end_at') or row['approval_status']=='active': continue
        start,end=week_bounds(row['start_at'])
        item=weeks.setdefault(start,dict(start=start,end=end,rows=[],minutes=0,unpaid=[],pending=[]))
        item['rows'].append(row)
        if row['approval_status']!='rejected': item['minutes']+=int(row.get('actual_minutes') or 0)
        if row['approval_status']=='approved' and row.get('payment_id') is None: item['unpaid'].append(row)
        if row['approval_status']=='pending': item['pending'].append(row)
    for item in weeks.values():
        item['amount']=total_amount(item['unpaid'])
        item['pending_amount']=total_amount(item['pending'])
        item['rows'].sort(key=lambda r:r['start_at'])
    return sorted(weeks.values(),key=lambda item:item['start'],reverse=True)


def migrate_unpaid(conn):
    name='minute-payroll-2026-10-17'
    if conn.execute('SELECT 1 FROM app_migrations WHERE name=?',(name,)).fetchone(): return
    rows=conn.execute("SELECT * FROM shifts WHERE payment_id IS NULL AND end_at IS NOT NULL AND approval_status!='active'").fetchall()
    for row in rows:
        # Already-created payouts and their shifts remain historical records.
        conn.execute('''INSERT INTO payroll_migration_backup(shift_id,actual_minutes,billable_hours,amount)
            VALUES(?,?,?,?) ON CONFLICT(shift_id) DO NOTHING''',(row['id'],row['actual_minutes'],row['billable_hours'],row['amount']))
        minutes,hours,amount=shift_values(row['start_at'],row['end_at'],row['hourly_rate'])
        conn.execute('UPDATE shifts SET actual_minutes=?,billable_hours=?,amount=? WHERE id=? AND payment_id IS NULL',
                     (minutes,hours,amount,row['id']))
    conn.execute('INSERT INTO app_migrations(name,applied_at) VALUES(?,?)',(name,datetime.now().isoformat(timespec='seconds')))
