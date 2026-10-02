from contextlib import contextmanager
import pandas as pd
import psycopg2
import streamlit as st


def get_connection():
    """Abre uma conexão nova com o PostgreSQL no Supabase utilizando os Secrets do Streamlit."""
    try:
        # Tenta buscar a URL do Supabase configurada nos Secrets do Streamlit
        database_url = st.secrets["DATABASE_URL"]
    except Exception:
        # Fallback caso esteja a rodar localmente e queira testar com outra string ou SQLite
        database_url = None

    if database_url:
        # Conexão oficial com o Supabase/PostgreSQL
        conn = psycopg2.connect(database_url)
        return conn
    else:
        raise RuntimeError(
            "DATABASE_URL não encontrada nos Secrets do Streamlit Cloud!"
        )


@contextmanager
def get_db():
    """Context manager para gerenciar transações com o Supabase."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
