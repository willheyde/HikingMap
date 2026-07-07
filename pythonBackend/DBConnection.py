# db/connection.py
import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# .env is the source of truth for local dev. override=True fixes the USER
# collision on Linux/macOS (a shell-provided USER would otherwise shadow the
# .env value). On AWS there is no .env file, so this is a no-op and the
# environment-injected values (Secrets Manager / SSM) are used as-is.
load_dotenv(override=True)


def _conn_kwargs() -> dict:
    # DB_USER is preferred over USER so that, when credentials are injected as
    # real environment variables (AWS), they never collide with the shell's
    # USER. USER stays as a local fallback for the existing .env layout.
    return {
        "host":        os.getenv("HOST"),
        "port":        os.getenv("PORT"),
        "dbname":      os.getenv("DBNAME"),
        "user":        os.getenv("DB_USER") or os.getenv("USER"),
        "password":    os.getenv("PASSWORD"),
        "row_factory": dict_row,
    }


# ── Connection pool (optional dependency) ─────────────────────────────────────
# psycopg_pool keeps a set of warm connections instead of opening a fresh TCP +
# auth handshake on every request — essential against a managed DB (RDS) under
# any real concurrency. It is an *optional* dependency: when it isn't installed
# we fall back to a direct connection per call (the original behavior), so the
# app still runs on a laptop that hasn't installed requirements.txt yet.
try:
    from psycopg_pool import ConnectionPool
    _HAS_POOL = True
except ImportError:                     # pragma: no cover - env without the pool lib
    _HAS_POOL = False

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo="",
            kwargs=_conn_kwargs(),
            min_size=int(os.getenv("DB_POOL_MIN", "1")),
            max_size=int(os.getenv("DB_POOL_MAX", "10")),
            open=False,
        )
        _pool.open()
    return _pool


def close_pool() -> None:
    """Close the pool and release its connections. Called on app shutdown; a
    no-op when pooling isn't in use."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_connection():
    """
    Yield a dict_row connection. On clean exit the transaction is committed; on
    error it is rolled back. Uses a warm connection pool when psycopg_pool is
    available, otherwise opens a direct connection per call. Both paths share
    identical commit/rollback semantics.
    """
    if _HAS_POOL:
        # pool.connection() enters the connection's own transaction block:
        # commit on clean exit, rollback on exception, then return it to the pool.
        with _get_pool().connection() as conn:
            yield conn
    else:
        conn = psycopg.connect(**_conn_kwargs())
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
