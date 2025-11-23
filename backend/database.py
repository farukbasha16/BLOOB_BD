import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to the database. {e}")
        return None

def fetch_all(query, params=None):
    """Executes a query and fetches all results."""
    conn = get_db_connection()
    if conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()
        conn.close()
        return results
    return []

def fetch_one(query, params=None):
    """Executes a query and fetches a single result."""
    conn = get_db_connection()
    if conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            result = cur.fetchone()
        conn.close()
        return result
    return None

def execute_query(query, params=None):
    """Executes a data modification query (INSERT, UPDATE, DELETE)."""
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
        conn.close()
        return True
    return False
