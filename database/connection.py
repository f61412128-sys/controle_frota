from contextlib import contextmanager
import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st


class Psycopg2CompatCursor(object):
    """Cursor wrapper para compatibilidade com padrões SQLite/Pandas."""
    def __init__(self, cursor, connection):
        self.cursor = cursor
        self.connection = connection

    def execute(self, query, vars=None):
        # Substitui placeholders do SQLite (?) por placeholders do PostgreSQL (%s) se necessário
        if "?" in query:
            query = query.replace("?", "%s")
        return self.cursor.execute(query, vars)

    def executemany(self, query, vars_list):
        if "?" in query:
            query = query.replace("?", "%s")
        return self.cursor.executemany(query, vars_list)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchmany(self, size=None):
        return self.cursor.fetchmany(size)

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def __iter__(self):
        return iter(self.cursor)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()


class Psycopg2CompatConnection(object):
    """Conexão wrapper que emula o comportamento do SQLite para o psycopg2."""
    def __init__(self, connection):
        self.connection = connection

    def cursor(self, *args, **kwargs):
        return Psycopg2CompatCursor(self.connection.cursor(*args, **kwargs), self.connection)

    def execute(self, query, vars=None):
        cur = self.cursor()
        cur.execute(query, vars)
        return cur

    def executescript(self, script):
        cur = self.cursor()
        cur.cursor.execute(script)
        return cur

    def commit(self):
        return self.connection.commit()

    def rollback(self):
        return self.connection.rollback()

    def close(self):
        return self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def get_connection():
    """Abre uma conexão nova com o PostgreSQL no Supabase utilizando os Secrets do Streamlit."""
    try:
        database_url = st.secrets["DATABASE_URL"]
    except Exception as e:
        raise RuntimeError(
            "DATABASE_URL não encontrada nos Secrets do Streamlit Cloud!"
        ) from e

    conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
    return Psycopg2CompatConnection(conn)


@contextmanager
def get_db():
    """Context manager para gerenciar transações e compatibilidade com o Supabase."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
