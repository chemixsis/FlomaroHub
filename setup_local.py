"""Run locally. Credentials never enter source files or terminal command history."""
from getpass import getpass
from pathlib import Path
import json
import re
from access_password import make_hash


def main():
    destination = Path(__file__).with_name('.streamlit') / 'secrets.toml'
    if destination.exists():
        raise SystemExit('Plik .streamlit/secrets.toml już istnieje. Nie nadpisano ustawień.')
    print('Konfiguracja lokalna. Podawane hasła nie będą wyświetlane.')
    email = input('E-mail właściciela (dla pierwszego konta szefa): ').strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise SystemExit('Niepoprawny e-mail.')
    database_password = getpass('Obecne hasło bazy Supabase: ')
    if not database_password:
        raise SystemExit('Brak hasła bazy.')
    password = getpass('Ustal osobne hasło dostępu do testów (minimum 16 znaków): ')
    if password != getpass('Powtórz hasło dostępu do testów: '):
        raise SystemExit('Hasła różnią się.')
    encoded = make_hash(password)
    settings = {
        'DB_HOST': 'aws-1-eu-west-1.pooler.supabase.com',
        'DB_PORT': 5432,
        'DB_NAME': 'postgres',
        'DB_USER': 'postgres.bnfzspmexvdhzkrpraas',
        'DB_PASSWORD': database_password,
        'BOOTSTRAP_EMAIL': email,
        'ACCESS_PASSWORD_HASH': encoded,
        'DATA_READY': False,
    }
    destination.parent.mkdir(exist_ok=True)
    with destination.open('x', encoding='utf-8') as handle:
        handle.write('# PRYWATNE: nie wysyłaj na GitHub ani do czatu.\n')
        for key, value in settings.items():
            handle.write(f'{key} = {json.dumps(value, ensure_ascii=False)}\n')
    print('Zapisano prywatny plik .streamlit/secrets.toml. Teraz wykonaj import danych.')


if __name__ == '__main__':
    main()
