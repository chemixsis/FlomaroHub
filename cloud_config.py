"""Secrets are read locally/server-side, never from committed configuration."""
import os
import time
from pathlib import Path

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'):
    time.tzset()


def setting(name, default=None):
    value = os.environ.get(name)
    if value is not None:
        return value
    secrets_file = Path(__file__).with_name('.streamlit') / 'secrets.toml'
    if secrets_file.exists():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with secrets_file.open('rb') as handle:
            return tomllib.load(handle).get(name, default)
    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except (ImportError, FileNotFoundError):
        return default


def database_settings():
    required = ('DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')
    values = {name: setting(name) for name in required}
    if not all(values.values()):
        raise RuntimeError('Brak konfiguracji bazy. Uzupełnij sekrety DB_HOST, DB_NAME, DB_USER i DB_PASSWORD.')
    return dict(host=values['DB_HOST'], dbname=values['DB_NAME'], user=values['DB_USER'],
                password=values['DB_PASSWORD'], port=int(setting('DB_PORT', 5432)),
                sslmode='require', connect_timeout=10, prepare_threshold=None)
