"""Registration/contact checks; no DNS requests during normal page rendering."""
import re
from email_validator import validate_email, EmailNotValidError, EmailUndeliverableError

TYPOS = {'gmail.con':'gmail.com','gmail.com.pl':'gmail.com','gmial.com':'gmail.com',
         'gamil.com':'gmail.com','gmai.com':'gmail.com','gmail.co':'gmail.com',
         'hotmail.con':'hotmail.com','outlook.con':'outlook.com','wp.p':'wp.pl','onet.p':'onet.pl'}


def checked_email(value, check_dns=True):
    value=str(value or '').strip().lower()
    domain=value.rsplit('@',1)[-1]
    if domain in TYPOS:
        raise ValueError(f'Prawdopodobna literówka w e-mailu: zamiast {domain} wpisz {TYPOS[domain]}. Sprawdź adres — nie zmieniamy go automatycznie.')
    try:
        result=validate_email(value,check_deliverability=check_dns,timeout=3,allow_smtputf8=False)
    except EmailUndeliverableError:
        raise ValueError('Domena tego e-maila nie przyjmuje poczty lub nie istnieje. Sprawdź adres.') from None
    except EmailNotValidError:
        raise ValueError('Podaj poprawny e-mail, np. imie@gmail.com, bez spacji i literówek.') from None
    if check_dns and not getattr(result,'mx',None):
        raise ValueError('Nie udało się teraz sprawdzić domeny e-maila. Spróbuj ponownie za chwilę.')
    return result.normalized.lower()


def sms_number(value):
    value=str(value or '').strip()
    if not re.fullmatch(r'[+0-9 ()-]+',value):
        raise ValueError('Niepoprawny numer telefonu.')
    digits=re.sub(r'\D','',value)
    if digits.startswith('00'):
        digits=digits[2:]
    elif len(digits)==9 and not value.startswith('+'):
        digits='48'+digits
    if not re.fullmatch(r'[1-9][0-9]{7,14}',digits):
        raise ValueError('Podaj numer z prefiksem kraju, np. +48 123 456 789.')
    return digits
