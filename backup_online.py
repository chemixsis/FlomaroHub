"""Export a consistent online snapshot into a new local SQLite file."""
from datetime import datetime
from pathlib import Path
import sqlite3
from uuid import uuid4
from migrate_data import TABLES, quoted
from postgres_backend import connect


def main():
    root = Path(__file__).resolve().parent
    folder = root / 'backups'
    folder.mkdir(exist_ok=True)
    target = folder / f"online-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.db"
    destination = sqlite3.connect(target)
    try:
        destination.executescript((root / 'sqlite_schema.sql').read_text(encoding='utf-8-sig'))
        with connect() as source, destination:
            source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            for table in TABLES:
                rows = source.execute(f'SELECT * FROM {quoted(table)}').fetchall()
                if rows:
                    columns = ','.join(map(quoted, rows[0].keys()))
                    placeholders = ','.join('?' for _ in rows[0])
                    destination.executemany(
                        f'INSERT INTO {quoted(table)} ({columns}) VALUES ({placeholders})',
                        [tuple(row.values()) for row in rows])
            if destination.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Niespójne powiązania w kopii.')
            if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Niepoprawna kopia.')
    except Exception as exc:
        destination.close()
        target.unlink(missing_ok=True)
        print('Nie utworzono kopii. Typ błędu:', type(exc).__name__)
        raise SystemExit(1)
    finally:
        destination.close()
    print('Kopia gotowa:', target)
    print('Plik zawiera dane pracowników. Zachowaj go prywatnie; nie wysyłaj na GitHub.')


if __name__ == '__main__':
    main()
