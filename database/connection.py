from contextlib import contextmanager
import pandas as pd
import psycopg2
import streamlit as st


def get_connection():
    """Abre uma conexão nova com o PostgreSQL no Supabase utilizando os Secrets do Streamlit."""
    try:
        database_url = st.secrets["DATABASE_URL"]
    except Exception as e:
        raise RuntimeError(
            "DATABASE_URL não encontrada nos Secrets do Streamlit Cloud!"
        ) from e

    conn = psycopg2.connect(database_url)
    return conn


@contextmanager
def get_db():
    """Context manager para gerenciar transações e cursores com o Supabase."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
