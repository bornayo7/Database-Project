"""Small MySQL boundary with explicit transaction ownership and cleanup."""
from contextlib import contextmanager
import os
import re

import mysql.connector
from flask import current_app


def settings():
    return dict(DB_HOST=os.getenv('DB_HOST', '127.0.0.1'), DB_PORT=int(os.getenv('DB_PORT', '3306')),
                DB_USER=os.getenv('DB_USER', 'dealership_app'), DB_PASSWORD=os.getenv('DB_PASSWORD', ''),
                DB_NAME=os.getenv('DB_NAME', 'cardealership'))


def connect(config=None):
    config = settings() if config is None else config
    return mysql.connector.connect(host=config['DB_HOST'], port=config['DB_PORT'],
                                   user=config['DB_USER'], password=config['DB_PASSWORD'], database=config['DB_NAME'],
                                   charset='utf8mb4', autocommit=False, connection_timeout=5, use_pure=True)


def identifier(value):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', value):
        raise ValueError('Database names must use letters, digits and underscores, starting with a letter.')
    return f'`{value}`'


@contextmanager
def cursor(write=False):
    """Roll back errors (including non-MySQL exceptions), close every acquired resource."""
    db = connect(current_app.config)
    cur = None
    try:
        cur = db.cursor(dictionary=True, buffered=True)
        yield cur
        if write:
            db.commit()
    except BaseException:
        try:
            db.rollback()
        except mysql.connector.Error:
            pass  # Preserve the original exception, not a disconnected rollback error.
        raise
    finally:
        try:
            if cur is not None:
                cur.close()
        finally:
            db.close()
