import os
from pathlib import Path

# Caminho base do projeto
BASE_DIR = Path(__file__).resolve().parent

# Banco de dados
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "frota.db"

# Uploads (o banco guarda só o caminho RELATIVO a esta pasta)
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOAD_SUBPASTAS = ["veiculos", "ocorrencias", "manutencoes"]

def garantir_pastas():
    """Cria as pastas necessárias, caso ainda não existam."""
    DATA_DIR.mkdir(exist_ok=True)
    for nome in UPLOAD_SUBPASTAS:
        (UPLOADS_DIR / nome).mkdir(parents=True, exist_ok=True)

# Garante a criação automática das pastas ao importar o config
garantir_pastas()