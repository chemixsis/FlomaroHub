"""Read-only SQLite import, with a local snapshot and transactional verification."""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from postgres_backend import connect, IDENTITY_TABLES

ROOT = Path(__file__).resolve().parent
TABLES = ('users', 'work_groups', 'user_work_groups', 'registration_requests',
          'schedules', 'events', 'event_assignments', 'event_attachments',
          'payments', 'availabilities', 'notifications', 'shifts')


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def fingerprint(rows):
    def normalized(value):
        if isinstance(value, (bytes, bytearray, memoryview)):
            return {'bytes': bytes(value).hex()}
        return value
    return Counter(hashlib.sha256(json.dumps(
        [normalized(value) for value in row], ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest() for row in rows)


def snapshot(source):
    source = Path(source).resolve(strict=True)
    if not source.is_file():
        raise ValueError('Źródło nie jest plikiem bazy.')
    backups = ROOT / 'backups'
    backups.mkdir(exist_ok=True)
    from uuid import uuid4
    target = backups / f"before-import-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.db"
    readonly = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    try:
        with closing(sqlite3.connect(target)) as destination, destination:
            readonly.backup(destination)
    finally:
        readonly.close()
    return target


def load_source(path):
    source = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Kontrola spójności SQLite nie powiodła się.')
        if source.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Źródłowa baza zawiera niespójne powiązania. Import zatrzymany.')
        names = {r[0] for r in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if names - set(TABLES):
            raise ValueError('Źródło zawiera dodatkowe tabele. Potrzebne sprawdzenie wersji bazy.')
        if not {'users', 'work_groups', 'shifts'}.issubset(names):
            raise ValueError('Plik nie jest rozpoznaną bazą FlomaroHUB.')
        result = {}
        for table in TABLES:
            if table in names:
                cursor = source.execute(f'SELECT * FROM {quoted(table)}')
                result[table] = ([c[0] for c in cursor.description], cursor.fetchall())
        return result
    finally:
        source.close()


def import_rows(data, connector=connect):
    # Schema creation and every row are part of one transaction. A mismatch rolls it all back.
    with connector() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(73190421)')
        conn.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8-sig'))
        for table in TABLES:
            if conn.execute(f'SELECT 1 FROM {quoted(table)} LIMIT 1').fetchone():
                raise ValueError('Supabase zawiera już dane FlomaroHUB. Niczego nie nadpisano.')
        counts = {}
        for table in TABLES:
            if table not in data:
                continue
            columns, rows = data[table]
            allowed = {r[0] for r in conn.execute(
                'SELECT column_name FROM information_schema.columns WHERE table_schema=? AND table_name=?',
                ('flomaro', table))}
            if set(columns) - allowed:
                raise ValueError(f'Tabela {table} zawiera dodatkowe kolumny. Import zatrzymany.')
            column_sql = ','.join(map(quoted, columns))
            placeholders = ','.join('?' for _ in columns)
            conn.executemany(f'INSERT INTO {quoted(table)} ({column_sql}) VALUES ({placeholders})', rows)
            actual = conn.execute(f'SELECT {column_sql} FROM {quoted(table)}').fetchall()
            if fingerprint(rows) != fingerprint([list(row.values()) for row in actual]):
                raise ValueError(f'Kontrola danych tabeli {table} nie powiodła się. Import wycofany.')
            counts[table] = len(rows)
        for table in IDENTITY_TABLES:
            maximum = conn.execute(f'SELECT MAX(id) FROM {quoted(table)}').fetchone()[0]
            conn.execute("SELECT setval(pg_get_serial_sequence(?, 'id'), ?, ?)",
                         ('flomaro.' + table, maximum or 1, maximum is not None))
        # Group IDs copied from SQLite remain unchanged; only absent groups are added.
        for code, name in (('event', 'Eventy'), ('local', 'Lokal'), ('warehouse', 'Magazyn')):
            conn.execute('INSERT OR IGNORE INTO work_groups(code,name) VALUES(?,?)', (code, name))
        return counts


def mark_ready():
    path = ROOT / '.streamlit' / 'secrets.toml'
    if path.exists():
        text = path.read_text(encoding='utf-8')
        if 'DATA_READY = false' in text:
            path.write_text(text.replace('DATA_READY = false', 'DATA_READY = true'), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Import FlomaroHUB bez zmieniania oryginalnego SQLite.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--source', help='Pełna ścieżka do istniejącego flomaro.db')
    group.add_argument('--empty', action='store_true', help='Świadomie rozpocznij testy bez starych danych')
    args = parser.parse_args()
    if args.source:
        backup = snapshot(args.source)
        print('Utworzono lokalną kopię zapasową:', backup)
        data = load_source(backup)
    else:
        data = {}
    try:
        counts = import_rows(data)
    except Exception as exc:
        # Database driver exceptions may contain private values, so do not print those.
        if isinstance(exc, ValueError):
            print(str(exc))
        else:
            print('Import nie powiódł się. Transakcja została wycofana. Sprawdź konfigurację i połączenie.')
            print('Typ błędu:', type(exc).__name__)
        raise SystemExit(1)
    mark_ready()
    print('Import zakończony i zweryfikowany. Liczby rekordów:', counts)
    print('Oryginalny plik pozostaje zachowany. Uruchom teraz sprawdzenie połączenia.')


if __name__ == '__main__':
    main()
