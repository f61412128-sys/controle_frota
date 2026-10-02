from contextlib import contextmanager
import psycopg2
import streamlit as st


def get_connection():
    """Abre uma conexão nova com o PostgreSQL no Supabase."""
    database_url = st.secrets["DATABASE_URL"]
    return psycopg2.connect(database_url)


@contextmanager
def get_db():
    """Context manager padrão para transações do PostgreSQL."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
