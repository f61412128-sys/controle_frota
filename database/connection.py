import sqlite3
from contextlib import contextmanager

from config import DB_PATH, garantir_pastas


def get_connection():
    """Abre uma conexão nova com o banco."""
    garantir_pastas()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # permite acessar colunas por nome
    conn.execute("PRAGMA foreign_keys = ON")  # ativa chaves estrangeiras
    return conn


@contextmanager
def get_db():
    """
    Uso:
        with get_db() as conn:
            conn.execute(...)
    Salva (commit) se tudo der certo, desfaz (rollback) se der erro,
    e sempre fecha a conexão.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()