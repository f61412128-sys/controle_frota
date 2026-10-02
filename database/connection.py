import os
import psycopg2
import psycopg2.extras
import streamlit as st


def get_connection():
    try:
        database_url = st.secrets["DATABASE_URL"]
    except Exception:
        database_url = os.getenv("DATABASE_URL")

    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.DictCursor)
