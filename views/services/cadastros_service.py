import sqlite3
from config import DB_PATH
from database.connection import get_connection

# =========================================================================
# AUTENTICAÇÃO E UTILIZADORES
# =========================================================================


def autenticar_usuario(login_input, senha_input):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM usuarios WHERE login = ?", (login_input,)
        )
        user = cursor.fetchone()
    finally:
        conn.close()

    if not user:
        return None

    user_dict = dict(user)
    campo_senha = "senha" if "senha" in user_dict else "senha_hash"

    if campo_senha in user_dict and str(user_dict[campo_senha]) == str(
        senha_input
    ):
        if "status" in user_dict and user_dict["status"] != "Ativo":
            return None
        return user_dict

    return None


def salvar_usuario(nome, login, senha, perfil="motorista"):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO usuarios (nome, login, senha_hash, perfil)
            VALUES (?, ?, ?, ?)
        """,
            (nome, login, senha, perfil),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def listar_usuarios():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios")
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


# =========================================================================
# MOTORISTAS
# =========================================================================


def listar_motoristas():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM motoristas")
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


def salvar_motorista(
    nome, cpf_matricula, telefone, cnh, categoria_cnh, validade_cnh
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO motoristas (nome, cpf_matricula, telefone, cnh, categoria_cnh, validade_cnh, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Ativo')
        """,
            (nome, cpf_matricula, telefone, cnh, categoria_cnh, validade_cnh),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def atualizar_motorista(
    motorista_id,
    nome,
    cpf_matricula,
    telefone,
    cnh,
    categoria_cnh,
    validade_cnh,
    status,
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE motoristas
            SET nome = ?, cpf_matricula = ?, telefone = ?, cnh = ?, categoria_cnh = ?, validade_cnh = ?, status = ?
            WHERE id = ?
        """,
            (
                nome,
                cpf_matricula,
                telefone,
                cnh,
                categoria_cnh,
                validade_cnh,
                status,
                motorista_id,
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# =========================================================================
# VEÍCULOS (ATUALIZADO COM GARANTIA DE COLUNAS)
# =========================================================================


def garantir_tabela_veiculos():
    """Garante que a tabela veiculos existe e possui todas as colunas de propriedade/locação."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS veiculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                placa TEXT,
                marca TEXT,
                modelo TEXT,
                ano INTEGER,
                tipo TEXT,
                cor TEXT,
                chassi TEXT,
                km_atual REAL,
                motorista_id INTEGER,
                status TEXT,
                tipo_propriedade TEXT,
                locadora TEXT,
                inicio_contrato TEXT,
                fim_contrato TEXT,
                valor_mensal REAL,
                FOREIGN KEY (motorista_id) REFERENCES motoristas (id)
            )
        """
        )

        # Verifica se as colunas novas existem em bases antigas e adiciona se faltarem
        cursor.execute("PRAGMA table_info(veiculos)")
        colunas_existentes = [col[1] for col in cursor.fetchall()]

        colunas_necessarias = {
            "tipo_propriedade": "TEXT",
            "locadora": "TEXT",
            "inicio_contrato": "TEXT",
            "fim_contrato": "TEXT",
            "valor_mensal": "REAL",
        }

        for coluna, tipo_dado in colunas_necessarias.items():
            if coluna not in colunas_existentes:
                cursor.execute(
                    f"ALTER TABLE veiculos ADD COLUMN {coluna} {tipo_dado}"
                )

        conn.commit()
    except Exception as e:
        print(f"Erro ao garantir tabela de veículos: {e}")
    finally:
        conn.close()


def listar_veiculos():
    garantir_tabela_veiculos()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT v.*, m.nome as motorista 
            FROM veiculos v 
            LEFT JOIN motoristas m ON v.motorista_id = m.id
        """
        )
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


def salvar_veiculo(
    placa,
    marca,
    modelo,
    ano,
    tipo,
    cor,
    chassi,
    km_atual,
    motorista_id,
    tipo_propriedade="Próprio",
    locadora=None,
    inicio_contrato=None,
    fim_contrato=None,
    valor_mensal=0.0,
    status="Disponível",
):
    garantir_tabela_veiculos()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO veiculos (
                placa, marca, modelo, ano, tipo, cor, chassi, km_atual, motorista_id, status,
                tipo_propriedade, locadora, inicio_contrato, fim_contrato, valor_mensal
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                placa,
                marca,
                modelo,
                ano,
                tipo,
                cor,
                chassi,
                km_atual,
                motorista_id,
                status,
                tipo_propriedade,
                locadora,
                str(inicio_contrato) if inicio_contrato else None,
                str(fim_contrato) if fim_contrato else None,
                valor_mensal,
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def atualizar_veiculo(
    veiculo_id,
    placa,
    marca,
    modelo,
    ano,
    tipo,
    cor,
    chassi,
    km_atual,
    motorista_id,
    tipo_propriedade="Próprio",
    locadora=None,
    inicio_contrato=None,
    fim_contrato=None,
    valor_mensal=0.0,
    status="Disponível",
):
    garantir_tabela_veiculos()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE veiculos
            SET placa = ?, marca = ?, modelo = ?, ano = ?, tipo = ?, cor = ?, chassi = ?, 
                km_atual = ?, motorista_id = ?, status = ?, tipo_propriedade = ?, 
                locadora = ?, inicio_contrato = ?, fim_contrato = ?, valor_mensal = ?
            WHERE id = ?
        """,
            (
                placa,
                marca,
                modelo,
                ano,
                tipo,
                cor,
                chassi,
                km_atual,
                motorista_id,
                status,
                tipo_propriedade,
                locadora,
                str(inicio_contrato) if inicio_contrato else None,
                str(fim_contrato) if fim_contrato else None,
                valor_mensal,
                veiculo_id,
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
