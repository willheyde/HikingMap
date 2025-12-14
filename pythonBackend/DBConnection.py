# db/connection.py
import psycopg
from psycopg.rows import dict_row

def get_connection():
    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname="hikingapp",
        user="WillH",
        password="12345",
        row_factory=dict_row,
    )
