from database.connection import get_db

STATUS_VEICULO = ["Disponível", "Em viagem", "Em manutenção", "Inativo"]
STATUS_MOTORISTA = ["Ativo", "Inativo"]
PERFIS = ["motorista", "responsavel", "administrador", "admin"]
RESULTADO_ITEM = ["OK", "NÃO OK", "N/A"]
RESULTADO_CHECKLIST = ["Aprovado", "Com pendências"]
GRAVIDADES = ["Baixa", "Média", "Alta", "Crítica"]
STATUS_OCORRENCIA = [
    "Aberto",
    "Em análise",
    "Em manutenção",
    "Resolvido",
    "Cancelado",
]
STATUS_MANUTENCAO = ["Agendada", "Em andamento", "Concluída", "Cancelada"]
TIPO_MANUTENCAO = ["Preventiva", "Corretiva"]
TIPO_PROPRIEDADE = ["Próprio", "Alugado", "Terceirizado"]


def _lista_sql(opcoes):
    return ", ".join(f"'{o}'" for o in opcoes)


SCHEMA = """
CREATE TABLE IF NOT EXISTS motoristas (
    id             SERIAL PRIMARY KEY,
    nome           TEXT NOT NULL,
    cpf_matricula  TEXT NOT NULL UNIQUE,
    telefone       TEXT,
    cnh            TEXT,
    categoria_cnh  TEXT,
    validade_cnh   TEXT,
    status         TEXT NOT NULL DEFAULT 'Ativo',
    criado_em      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usuarios (
    id             SERIAL PRIMARY KEY,
    nome           TEXT NOT NULL,
    login          TEXT NOT NULL UNIQUE,
    senha_hash     TEXT NOT NULL,
    perfil         TEXT NOT NULL,
    motorista_id   INTEGER,
    ativo          INTEGER NOT NULL DEFAULT 1,
    criado_em      TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS veiculos (
    id                   SERIAL PRIMARY KEY,
    placa                TEXT NOT NULL UNIQUE,
    marca                TEXT NOT NULL,
    modelo               TEXT NOT NULL,
    ano                  INTEGER,
    tipo                 TEXT,
    cor                  TEXT,
    chassi               TEXT,
    km_atual             INTEGER NOT NULL DEFAULT 0,
    motorista_id         INTEGER,
    status               TEXT NOT NULL DEFAULT 'Disponível',
    tipo_propriedade     TEXT NOT NULL DEFAULT 'Próprio',
    locadora             TEXT,
    inicio_contrato      TEXT,
    fim_contrato         TEXT,
    valor_mensal         REAL DEFAULT 0.0,
    foto_path            TEXT,
    criado_em            TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS checklists (
    id            SERIAL PRIMARY KEY,
    veiculo_id    INTEGER NOT NULL,
    motorista_id  INTEGER NOT NULL,
    data_hora     TIMESTAMP NOT NULL DEFAULT NOW(),
    km            INTEGER NOT NULL,
    resultado     TEXT NOT NULL DEFAULT 'Aprovado',
    observacoes   TEXT,
    localizacao   TEXT,
    FOREIGN KEY (veiculo_id)    REFERENCES veiculos(id),
    FOREIGN KEY (motorista_id) REFERENCES motoristas(id)
);

CREATE TABLE IF NOT EXISTS itens_checklist (
    id            SERIAL PRIMARY KEY,
    checklist_id  INTEGER NOT NULL,
    categoria     TEXT NOT NULL,
    item          TEXT NOT NULL,
    resultado     TEXT NOT NULL,
    FOREIGN KEY (checklist_id) REFERENCES checklists(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ocorrencias (
    id                  SERIAL PRIMARY KEY,
    veiculo_id          INTEGER NOT NULL,
    motorista_id        INTEGER NOT NULL,
    checklist_id        INTEGER,
    item_checklist_id   INTEGER,
    data_hora           TIMESTAMP NOT NULL DEFAULT NOW(),
    km                  INTEGER,
    categoria           TEXT,
    item                TEXT NOT NULL,
    descricao           TEXT NOT NULL,
    gravidade           TEXT NOT NULL DEFAULT 'Média',
    foto_path           TEXT,
    status              TEXT NOT NULL DEFAULT 'Aberto',
    atualizado_em       TIMESTAMP,
    FOREIGN KEY (veiculo_id)        REFERENCES veiculos(id),
    FOREIGN KEY (motorista_id)      REFERENCES motoristas(id),
    FOREIGN KEY (checklist_id)      REFERENCES checklists(id) ON DELETE SET NULL,
    FOREIGN KEY (item_checklist_id) REFERENCES itens_checklist(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS manutencoes (
    id                 SERIAL PRIMARY KEY,
    veiculo_id         INTEGER NOT NULL,
    ocorrencia_id      INTEGER,
    tipo               TEXT NOT NULL DEFAULT 'Preventiva',
    problema           TEXT NOT NULL,
    data_entrada       TEXT NOT NULL,
    km                 INTEGER,
    oficina            TEXT,
    responsavel        TEXT,
    pecas_utilizadas   TEXT,
    servico_realizado  TEXT,
    valor              REAL DEFAULT 0.0,
    proxima_data       TEXT,
    proximo_km         INTEGER,
    data_conclusao     TEXT,
    observacoes        TEXT,
    status             TEXT NOT NULL DEFAULT 'Em andamento',
    criado_em          TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (veiculo_id)    REFERENCES veiculos(id),
    FOREIGN KEY (ocorrencia_id) REFERENCES ocorrencias(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_checklists_veiculo  ON checklists(veiculo_id, data_hora);
CREATE INDEX IF NOT EXISTS idx_itens_checklist     ON itens_checklist(checklist_id);
CREATE INDEX IF NOT EXISTS idx_ocorrencias_veiculo ON ocorrencias(veiculo_id, status);
CREATE INDEX IF NOT EXISTS idx_manutencoes_veiculo ON manutencoes(veiculo_id);
"""


def init_db():
    """Cria as tabelas no PostgreSQL se ainda não existirem."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)


def contar_registros():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
            tabelas = cur.fetchall()

            resultado = {}
            for t in tabelas:
                nome_tabela = t[0]
                cur.execute(f"SELECT COUNT(*) FROM {nome_tabela}")
                qtd = cur.fetchone()[0]
                resultado[nome_tabela] = qtd

            return resultado


if __name__ == "__main__":
    init_db()
    print("Banco de dados inicializado com sucesso.")
