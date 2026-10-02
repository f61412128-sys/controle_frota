import os
import psycopg2
import psycopg2.extras
import streamlit as st


def get_connection():
    # Tenta ler do secrets do Streamlit Cloud ou da variável de ambiente local
    database_url = (
        st.secrets["DATABASE_URL"]
        if "DATABASE_URL" in st.secrets
        else os.getenv("DATABASE_URL")
    )
    # Retorna uma conexão com dicionário ativado (DictCursor) para facilitar o acesso por nome de coluna
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.DictCursor)
