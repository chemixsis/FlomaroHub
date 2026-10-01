"""Small compatibility layer for the app's parameterized SQL queries.

Postgres is the only backend in this deployment; no temporary SQLite fallback.
"""
import re
import sqlite3
import atexit
import threading
from datetime import date, datetime
from cloud_config import database_settings

IDENTITY_TABLES = frozenset(('users', 'work_groups', 'schedules', 'events', 'event_attachments',
                             'payments', 'availabilities', 'notifications', 'shifts'))


def translate_sql(sql, bound=False):
    # This project uses SQL literals with doubled single quotes and qmark bindings.
    if bound:
        sql = sql.replace('%', '%%')
    parts = re.split(r"('(?:''|[^'])*')", sql)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace('?', '%s')
    sql = ''.join(parts).strip().rstrip(';')
    sql = sql.replace('GROUP_CONCAT(', 'STRING_AGG(')
    if 'AS people' in sql and 'GROUP BY e.id' in sql:
        sql = sql.replace('GROUP BY e.id', 'GROUP BY e.id, m.first_name, m.last_name')
    if re.match(r'INSERT\s+OR\s+IGNORE\s+INTO', sql, re.I):
        sql = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', sql, count=1, flags=re.I)
        sql += ' ON CONFLICT DO NOTHING'
    match = re.match(r'INSERT\s+INTO\s+(\w+)', sql, re.I)
    returning = bool(match and match.group(1).lower() in IDENTITY_TABLES)
    if returning:
        sql += ' RETURNING id'
    return sql, returning


class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def row_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    def make_row(values):
        return Row((name, value.isoformat() if isinstance(value, (date, datetime)) else value)
                   for name, value in zip(names, values))
    return make_row


class Result:
    def __init__(self, cursor, returning=False):
        self.cursor = cursor
        self.lastrowid = None
        if returning:
            row = cursor.fetchone()
            self.lastrowid = row[0] if row else None
    @property
    def rowcount(self):
        return self.cursor.rowcount
    def fetchone(self):
        return self.cursor.fetchone()
    def fetchall(self):
        return self.cursor.fetchall()
    def __iter__(self):
        return iter(self.cursor)


class Connection:
    def __init__(self, raw, release=None):
        self.raw = raw
        self.release = release
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type:
                self.raw.rollback()
            else:
                self.raw.commit()
        finally:
            if self.release is None:
                self.raw.close()
            else:
                self.release(self.raw)
    def execute(self, sql, params=()):
        import psycopg
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            # The SQLite code used a write lock for registration/contact/event changes.
            return Result(self.raw.execute('SELECT pg_advisory_xact_lock(73190421)'))
        query, returning = translate_sql(sql, bound=bool(params))
        try:
            cursor = self.raw.execute(query, params) if params else self.raw.execute(query)
            return Result(cursor, returning)
        except psycopg.IntegrityError as exc:
            raise sqlite3.IntegrityError('Naruszenie spójności danych.') from None
    def executemany(self, sql, rows):
        for row in rows:
            self.execute(sql, row)
    def executescript(self, script):
        for sql in script.split(';'):
            if sql.strip():
                self.execute(sql)


_pool = None
_pool_lock = threading.Lock()


def configure_connection(raw):
    # Run once per physical connection, not on each query or page interaction.
    raw.execute('SET search_path TO flomaro, pg_catalog')
    raw.execute("SET TIME ZONE 'Europe/Warsaw'")
    raw.commit()


def get_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            from psycopg_pool import ConnectionPool
            pool = ConnectionPool(
                kwargs=dict(database_settings(), row_factory=row_factory),
                min_size=1, max_size=4, timeout=15,
                max_idle=300, max_lifetime=1800,
                configure=configure_connection,
                check=ConnectionPool.check_connection,
                open=False,
            )
            pool.open()
            atexit.register(pool.close)
            _pool = pool
        return _pool


def connect():
    pool = get_pool()
    return Connection(pool.getconn(), release=pool.putconn)
