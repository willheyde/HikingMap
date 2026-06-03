# db/connection.py
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
from dotenv import load_dotenv
import os
load_dotenv()
@contextmanager
def get_connection():
    conn = psycopg.connect(
        host=os.getenv("HOST"),
        port=os.getenv("PORT"),
        dbname=os.getenv("DBNAME"),
        user=os.getenv("USER"),
        password=os.getenv("PASSWORD"),
        row_factory=dict_row,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()