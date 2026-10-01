def carregar_dados_dashboard():
    """Busca os dados e indicadores direto do banco SQLite com total flexibilidade."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Contadores de veículos
    qtd_veiculos = cursor.execute(
        "SELECT COUNT(*) FROM veiculos WHERE status != 'Inativo'"
    ).fetchone()[0]

    qtd_proprios = cursor.execute(
        "SELECT COUNT(*) FROM veiculos WHERE status != 'Inativo' AND LOWER(tipo_propriedade) LIKE '%proprio%'"
    ).fetchone()[0]

    # Torna a busca de alugados e terceirizados flexível a acentos e maiúsculas
    qtd_alugados = cursor.execute(
        """
        SELECT COUNT(*) FROM veiculos 
        WHERE status != 'Inativo' 
          AND (LOWER(tipo_propriedade) LIKE '%alugado%' OR LOWER(tipo_propriedade) LIKE '%terceirizado%')
    """
    ).fetchone()[0]

    # Contadores de motoristas
    qtd_motoristas = cursor.execute(
        "SELECT COUNT(*) FROM motoristas WHERE status = 'Ativo'"
    ).fetchone()[0]

    try:
        qtd_manut_andamento = cursor.execute(
            "SELECT COUNT(*) FROM manutencoes WHERE LOWER(status) LIKE '%andamento%'"
        ).fetchone()[0]
        
        # Soma todos os valores de manutenções cadastradas para garantir que o custo aparece
        custo_total_manut = (
            cursor.execute(
                "SELECT SUM(valor) FROM manutencoes"
            ).fetchone()[0]
            or 0.0
        )
    except Exception:
        qtd_manut_andamento = 0
        custo_total_manut = 0.0

    # Ocorrências pendentes
    try:
        qtd_pendencias = cursor.execute(
            "SELECT COUNT(*) FROM ocorrencias WHERE LOWER(status) IN ('pendente', 'aberto', 'em análise')"
        ).fetchone()[0]
    except Exception:
        qtd_pendencias = 0

    # Busca de veículos e contratos
    try:
        df_veiculos_completo = pd.read_sql_query(
            """
            SELECT placa, marca, modelo, tipo_propriedade, locadora, inicio_contrato, fim_contrato, valor_mensal 
            FROM veiculos 
            WHERE status != 'Inativo'
            """,
            conn,
        )
    except Exception:
        df_veiculos_completo = pd.DataFrame()

    # Busca dinâmica das últimas manutenções
    try:
        df_m_raw = pd.read_sql_query(
            "SELECT m.*, v.placa, v.modelo FROM manutencoes m JOIN veiculos v ON m.veiculo_id = v.id ORDER BY m.id DESC LIMIT 10",
            conn,
        )
        if not df_m_raw.empty:
            cols = {}
            if "placa" in df_m_raw.columns:
                cols["placa"] = "Placa"
            if "modelo" in df_m_raw.columns:
                cols["modelo"] = "Veículo"
            if "problema" in df_m_raw.columns:
                cols["problema"] = "Serviço"
            elif "descricao" in df_m_raw.columns:
                cols["descricao"] = "Serviço"
            if "oficina" in df_m_raw.columns:
                cols["oficina"] = "Oficina"
            if "valor" in df_m_raw.columns:
                cols["valor"] = "Valor (R$)"
            if "status" in df_m_raw.columns:
                cols["status"] = "Status"
            if "data_entrada" in df_m_raw.columns:
                cols["data_entrada"] = "Data Entrada"

            df_manutencoes = df_m_raw[list(cols.keys())].rename(columns=cols)
        else:
            df_manutencoes = pd.DataFrame()
    except Exception:
        df_manutencoes = pd.DataFrame()

    conn.close()

    # Calcular contratos a vencer
    qtd_contratos_atencao = 0
    if not df_veiculos_completo.empty:
        df_alug = df_veiculos_completo[
            df_veiculos_completo["tipo_propriedade"]
            .str.lower()
            .str.contains("alugado|terceirizado", na=False)
        ]
        if not df_alug.empty:
            hoje = datetime.date.today()
            limite = hoje + datetime.timedelta(days=30)
            df_alug["fim_dt"] = pd.to_datetime(
                df_alug["fim_contrato"], errors="coerce"
            ).dt.date
            qtd_contratos_atencao = len(
                df_alug[df_alug["fim_dt"] <= limite]
            )

    return {
        "veiculos": qtd_veiculos,
        "proprios": qtd_proprios,
        "alugados": qtd_alugados,
        "contratos_atencao": qtd_contratos_atencao,
        "motoristas": qtd_motoristas,
        "manut_andamento": qtd_manut_andamento,
        "custo_total": custo_total_manut,
        "pendencias": qtd_pendencias,
        "df_manutencoes": df_manutencoes,
        "df_veiculos_completo": df_veiculos_completo,
    }
