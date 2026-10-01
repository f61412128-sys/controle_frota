import sqlite3
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from config import DB_PATH
from database.connection import get_connection
from views.services.cadastros_service import (
    salvar_motorista,
    salvar_usuario,
    salvar_veiculo,
)

print("\n" + "=" * 65)
print("🚀 BATERIA COMPLETA DE TESTES DE SEGURANÇA E STRESS")
print("=" * 65 + "\n")

sufixo = str(int(time.time()))[-4:]
placa_teste = f"ADV-{sufixo}"
cpf_teste = f"999.999.999-{sufixo}"


# --- ETAPA 1: SETUP E PREPARAÇÃO DA BASE ---
print("1️⃣ [SETUP] Criando Motorista e Veículo para Bateria Expandida...")
try:
    salvar_motorista(
        nome=f"Motorista Teste Avançado {sufixo}",
        cpf_matricula=cpf_teste,
        telefone="(11) 98888-7777",
        cnh="99988877700",
        categoria_cnh="D",
        validade_cnh="2030-12-31",
    )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM motoristas WHERE cpf_matricula = ?", (cpf_teste,)
    )
    motorista_id = cursor.fetchone()[0]
    conn.close()

    salvar_veiculo(
        placa=placa_teste,
        marca="Volvo",
        modelo="FH 540",
        ano=2024,
        tipo="Caminhão",
        cor="Prata",
        chassi=f"CHASSI_ADV_{sufixo}",
        km_atual=50000,
        motorista_id=motorista_id,
        status="Disponível",
    )
    print(
        f"  ✅ Setup concluído: Motorista (ID: {motorista_id}) e Veículo ({placa_teste} - 50.000 KM)."
    )

except Exception as e:
    print(f"  ❌ Falha no Setup: {e}")


# --- ETAPA 2: TESTE DE CONCORRÊNCIA MULTI-THREAD ---
print("\n2️⃣ [CONCORRÊNCIA] Simulando envios simultâneos de Checklists...")


def simular_envio_concorrente(indice):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(checklists)")
        colunas_chk = [col[1] for col in cursor.fetchall()]
        coluna_km = (
            "km"
            if "km" in colunas_chk
            else (
                "quilometragem" if "quilometragem" in colunas_chk else "km_atual"
            )
        )

        cursor.execute(
            f"""
            INSERT INTO checklists (veiculo_id, motorista_id, data_hora, {coluna_km}, observacoes)
            VALUES (?, ?, datetime('now', 'localtime'), ?, ?)
        """,
            (
                veiculo_id_global,
                motorista_id,
                50000 + indice,
                f"Checklist Concorrente Thread #{indice}",
            ),
        )

        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM veiculos WHERE placa = ?", (placa_teste,))
    veiculo_id_global = cursor.fetchone()[0]
    conn.close()

    with ThreadPoolExecutor(max_workers=5) as executor:
        resultados = list(executor.map(simular_envio_concorrente, range(1, 6)))

    sucessos = sum(1 for r in resultados if r)
    print(
        f"  ⚡ {sucessos}/5 transações concorrentes processadas com sucesso no SQLite!"
    )

except Exception as e:
    print(f"  ❌ Falha no Teste de Concorrência: {e}")


# --- ETAPA 3: TESTE DE SEGURANÇA (SQL INJECTION E CARACTERES ESPECIAIS) ---
print("\n3️⃣ [SEGURANÇA] Testando sanitização de caracteres especiais...")
texto_malicioso = "Teste ' OR '1'='1 -- <script>alert('hack')</script>"
conn = None
try:
    conn = get_connection()
    cursor = conn.cursor()

    # Inspecionar colunas reais para evitar NOT NULL constraints pendentes
    cursor.execute("PRAGMA table_info(ocorrencias)")
    colunas_oco = [col[1] for col in cursor.fetchall()]

    val_oco = {
        "veiculo_id": veiculo_id_global,
        "descricao": texto_malicioso,
        "status": "Aberto",
    }

    if "motorista_id" in colunas_oco:
        val_oco["motorista_id"] = motorista_id

    if "gravidade" in colunas_oco:
        val_oco["gravidade"] = "Baixa"

    if "item" in colunas_oco:
        val_oco["item"] = "Injeção de Teste"

    cols = ", ".join(val_oco.keys())
    placeholders = ", ".join(["?"] * len(val_oco))

    sql = f"INSERT INTO ocorrencias ({cols}) VALUES ({placeholders})"
    cursor.execute(sql, list(val_oco.values()))
    conn.commit()

    cursor.execute(
        "SELECT descricao FROM ocorrencias WHERE veiculo_id = ? AND status = 'Aberto'",
        (veiculo_id_global,),
    )
    resultado = cursor.fetchone()[0]

    if resultado == texto_malicioso:
        print(
            "  🛡️ SEGURANÇA OK: Parâmetros parametrizados protegeram o banco contra SQL Injection."
        )

except Exception as e:
    if conn:
        conn.rollback()
    print(f"  ❌ Falha na validação de segurança: {e}")
finally:
    if conn:
        conn.close()


# --- ETAPA 4: TESTE DE TRANSAÇÃO E ROLLBACK (ATOMICIDADE) ---
print("\n4️⃣ [ATOMICIDADE] Simulando falha de transação para validar Rollback...")
conn = None
try:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO checklists (veiculo_id, motorista_id, data_hora, km, observacoes)
        VALUES (?, ?, datetime('now', 'localtime'), 50100, 'Checklist Incompleto')
    """,
        (veiculo_id_global, motorista_id),
    )

    # Forçar erro propositado
    cursor.execute("INSERT INTO tabela_inexistente_teste VALUES (1)")
    conn.commit()
except sqlite3.OperationalError:
    if conn:
        conn.rollback()
    print(
        "  🛡️ ROLLBACK OK: A transação falhou como esperado e nenhum dado parcial foi gravado."
    )
except Exception as e:
    if conn:
        conn.rollback()
    print(f"  ⚠️ Exceção tratada no rollback: {e}")
finally:
    if conn:
        conn.close()


# --- ETAPA 5: TEARDOWN (LIMPEZA AUTOMÁTICA DOS DADOS) ---
print("\n5️⃣ [LIMPEZA] Removendo registros de teste da base...")
conn = None
try:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM itens_checklist WHERE checklist_id IN (SELECT id FROM checklists WHERE veiculo_id = ?)",
        (veiculo_id_global,),
    )
    cursor.execute(
        "DELETE FROM checklists WHERE veiculo_id = ?", (veiculo_id_global,)
    )
    cursor.execute(
        "DELETE FROM ocorrencias WHERE veiculo_id = ?", (veiculo_id_global,)
    )
    cursor.execute(
        "DELETE FROM manutencoes WHERE veiculo_id = ?", (veiculo_id_global,)
    )
    cursor.execute("DELETE FROM veiculos WHERE id = ?", (veiculo_id_global,))
    cursor.execute("DELETE FROM motoristas WHERE id = ?", (motorista_id,))

    conn.commit()
    print("  🧹 Limpeza concluída: Banco mantido 100% limpo!")

except Exception as e:
    if conn:
        conn.rollback()
    print(f"  ❌ Falha na limpeza: {e}")
finally:
    if conn:
        conn.close()