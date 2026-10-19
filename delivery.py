"""Transactional notification outbox. Network work runs outside Streamlit reruns."""
import json
import re
import threading
import time
import unicodedata
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from uuid import uuid4
from datetime import datetime
from zoneinfo import ZoneInfo
from postgres_backend import connect, read_connection
from contact_validation import checked_email, sms_number

SUPPORT_EMAIL='arinametluk@gmail.com'


def enqueue(conn, channel, recipient, subject, body, *, user_id=None,event_id=None,job_id=None):
    job_id=job_id or str(uuid4())
    conn.execute('''INSERT INTO delivery_outbox(id,channel,recipient,subject,body,user_id,event_id,status,created_at,next_attempt)
        VALUES(?,?,?,?,?,?,?,'queued',?,0) ON CONFLICT(id) DO NOTHING''',
        (job_id,channel,recipient,subject,body,user_id,event_id,int(time.time())))
    return job_id


def enqueue_assignment(conn,event_id,user_id):
    person=conn.execute('SELECT email,phone FROM users WHERE id=? AND active=1',(user_id,)).fetchone()
    event=conn.execute('SELECT name,event_date,start_time,end_time,location FROM events WHERE id=?',(event_id,)).fetchone()
    if not person or not event: return
    details=f"Przypisano Cię do eventu „{event['name']}”.\nData: {event['event_date']}\nGodziny: {event['start_time']}–{event['end_time']}\nMiejsce: {event['location'] or 'Sprawdź w aplikacji'}\nSzczegóły znajdziesz w FlomaroHUB."
    enqueue(conn,'email',person['email'],'FlomaroHUB — przypisanie do eventu',details,user_id=user_id,event_id=event_id)
    # Short ASCII SMS avoids accidental multi-part Unicode billing; full details in email/app.
    title=unicodedata.normalize('NFKD',event['name'].replace('ł','l').replace('Ł','L')).encode('ascii','ignore').decode()
    title=re.sub(r'[^a-zA-Z0-9 .,\-]',' ',title)
    title=' '.join(title.split())[:42]
    message=f"FlomaroHUB: przypisano Cie do eventu {title}, {event['event_date']} {event['start_time']}-{event['end_time']}. Szczegoly w aplikacji."
    enqueue(conn,'sms',person['phone'],'',message[:160],user_id=user_id,event_id=event_id)


def submit_problem(user_id,subject,description,page,token):
    subject=subject.strip(); description=description.strip()
    if not 3<=len(subject)<=120 or not 10<=len(description)<=5000:
        return False,'Podaj temat (3–120 znaków) i opis problemu (10–5000 znaków).'
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        user=conn.execute('SELECT first_name,last_name,email,access_level FROM users WHERE id=? AND active=1',(user_id,)).fetchone()
        if not user: return False,'Zaloguj się ponownie.'
        if conn.execute('SELECT id FROM support_tickets WHERE id=? AND user_id=?',(token,user_id)).fetchone():
            return True,'Zgłoszenie zostało już zapisane.'
        if conn.execute('SELECT count(*) FROM support_tickets WHERE user_id=? AND created_at>?',(user_id,int(time.time())-3600)).fetchone()[0]>=5:
            return False,'Możesz wysłać maksymalnie 5 zgłoszeń w ciągu godziny.'
        conn.execute('INSERT INTO support_tickets(id,user_id,subject,description,page,created_at) VALUES(?,?,?,?,?,?)',
                     (token,user_id,subject,description,page[:80],int(time.time())))
        body=f"Zgłoszenie {token}\nOd: {user['first_name']} {user['last_name']} ({user['email']})\nEkran: {page[:80]}\n\n{description}"
        enqueue(conn,'email',SUPPORT_EMAIL,'FlomaroHUB — problem: '+subject,body,user_id=user_id,job_id=token)
    return True,'Zgłoszenie zapisane. Trafi na e-mail pomocy po przetworzeniu kolejki.'


class SendFailure(Exception):
    def __init__(self,code,retry=False): self.code=code; self.retry=retry


def configured(channel,config):
    if channel=='email': return bool(config.get('RESEND_API_KEY') and config.get('EMAIL_FROM'))
    return bool(config.get('SMSAPI_TOKEN') and config.get('SMSAPI_SENDER'))


def send_job(job,config,opener=urlopen):
    if job['channel']=='email':
        try: recipient=checked_email(job['recipient'],check_dns=False)
        except ValueError: raise SendFailure('invalid_email') from None
        data=json.dumps({'from':config['EMAIL_FROM'],'to':[recipient],'subject':job['subject'],'text':job['body']}).encode()
        request=Request('https://api.resend.com/emails',data=data,method='POST',headers={
            'Authorization':'Bearer '+config['RESEND_API_KEY'],'Content-Type':'application/json',
            'Idempotency-Key':'flomaro/'+job['id'],'User-Agent':'FlomaroHUB/1.0'})
    else:
        try: recipient=sms_number(job['recipient'])
        except ValueError: raise SendFailure('invalid_phone') from None
        data=urlencode({'to':recipient,'message':job['body'],'from':config['SMSAPI_SENDER'],
                        'format':'json','encoding':'utf-8','idx':job['id'],'check_idx':1}).encode()
        request=Request('https://api.smsapi.pl/sms.do',data=data,method='POST',headers={
            'Authorization':'Bearer '+config['SMSAPI_TOKEN'],'Content-Type':'application/x-www-form-urlencoded',
            'User-Agent':'FlomaroHUB/1.0'})
    try:
        with opener(request,timeout=10) as response: result=json.loads(response.read())
    except HTTPError as exc:
        raise SendFailure('http_'+str(exc.code),retry=exc.code==429 or exc.code>=500) from None
    except Exception:
        raise SendFailure('network_or_response_error',retry=True) from None
    if job['channel']=='sms':
        if result.get('error'):
            if str(result['error'])=='53': return 'duplicate_accepted'
            raise SendFailure('smsapi_'+str(result['error']))
        if result.get('count')!=1 or not result.get('list'):
            raise SendFailure('sms_unconfirmed',retry=True)
        return str(result['list'][0]['id'])
    if not result.get('id'): raise SendFailure('email_unconfirmed',retry=True)
    return str(result['id'])


def process_one(config,connector=connect,sender=send_job,now=None):
    now=int(time.time()) if now is None else now
    channels=[c for c in ('email','sms') if configured(c,config)]
    if not channels: return False
    with connector() as conn:
        placeholders=','.join('?' for _ in channels)
        # A crash after provider acceptance is retried with the same idempotency key.
        job=conn.execute(f'''SELECT * FROM delivery_outbox WHERE channel IN ({placeholders})
            AND ((status='queued' AND next_attempt<=?) OR (status='sending' AND lease_until<?))
            ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED''',(*channels,now,now)).fetchone()
        if not job: return False
        job=dict(job)
        if job['first_attempt'] and now-job['first_attempt']>=23*3600:
            conn.execute("UPDATE delivery_outbox SET status='unknown',last_error='review_provider_before_retry' WHERE id=?",(job['id'],))
            return True
        if job['event_id'] is not None:
            today=datetime.fromtimestamp(now,ZoneInfo('Europe/Warsaw')).date().isoformat()
            eligible=conn.execute('''SELECT 1 FROM event_assignments a JOIN users u ON u.id=a.user_id
                JOIN events e ON e.id=a.event_id
                WHERE a.event_id=? AND a.user_id=? AND u.active=1 AND e.event_date>=?''',(job['event_id'],job['user_id'],today)).fetchone()
            if not eligible:
                conn.execute("UPDATE delivery_outbox SET status='cancelled' WHERE id=?",(job['id'],)); return True
        conn.execute("UPDATE delivery_outbox SET status='sending',attempts=attempts+1,first_attempt=?,lease_until=? WHERE id=?",
                     (job['first_attempt'] or now,now+120,job['id']))
    try:
        provider_id=sender(job,config)
        status,error,next_attempt='sent','',0
    except SendFailure as exc:
        status='queued' if exc.retry and job['attempts']<5 else 'failed'
        provider_id='';error=exc.code;next_attempt=now+min(3600,60*2**job['attempts'])
    except Exception:
        status,provider_id,error,next_attempt='unknown','','unexpected_sender_error',0
    with connector() as conn:
        conn.execute('UPDATE delivery_outbox SET status=?,provider_id=?,last_error=?,next_attempt=?,lease_until=0 WHERE id=?',
                     (status,provider_id,error,next_attempt,job['id']))
    return True


def delivery_status(actor_id):
    with read_connection() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id=? AND active=1 AND access_level='admin'",(actor_id,)).fetchone(): return []
        return conn.execute('SELECT channel,status,count(*) AS count FROM delivery_outbox GROUP BY channel,status ORDER BY channel,status').fetchall()


class DeliveryWorker:
    def __init__(self,config):
        self.config=config; self.wake=threading.Event()
        self.thread=threading.Thread(target=self.run,name='flomaro-delivery',daemon=True)
        self.thread.start()
    def run(self):
        while True:
            try:
                for _ in range(20):
                    if not process_one(self.config): break
            except Exception:
                pass  # Durable queue retained. Never print credentials or message contents.
            self.wake.wait(15); self.wake.clear()
