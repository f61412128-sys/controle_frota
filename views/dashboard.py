import datetime
import sqlite3
import pandas as pd
import streamlit as st
from database.connection import get_connection


def carregar_dados_dashboard():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Contadores de veículos (Consulta original exata)
    qtd_veiculos = cursor.execute(
        "SELECT COUNT(*) FROM veiculos WHERE status != 'Inativo'"
    ).fetchone()[0]

    qtd_proprios = cursor.execute(
        "SELECT COUNT(*) FROM veiculos WHERE status != 'Inativo' AND (LOWER(tipo_propriedade) LIKE '%proprio%' OR LOWER(tipo_propriedade) LIKE '%próprio%')"
    ).fetchone()[0]

    qtd_alugados = cursor.execute(
        """
        SELECT COUNT(*) FROM veiculos 
        WHERE status != 'Inativo' 
          AND (LOWER(tipo_propriedade) LIKE '%alugado%' OR LOWER(tipo_propriedade) LIKE '%terceirizado%' OR LOWER(tipo_propriedade) LIKE '%locado%')
    """
    ).fetchone()[0]

    # Motoristas
    try:
        qtd_motoristas = cursor.execute(
            "SELECT COUNT(*) FROM motoristas WHERE status = 'Ativo'"
        ).fetchone()[0]
    except Exception:
        qtd_motoristas = 0

    # Manutenções em andamento
    qtd_manut_andamento = 0
    try:
        qtd_manut_andamento = cursor.execute(
            "SELECT COUNT(*) FROM manutencoes WHERE LOWER(status) LIKE '%andamento%'"
        ).fetchone()[0]
    except Exception:
        pass

    # Custo Total de Manutenção (Lógica exata original)
    custo_total_manut = 0.0
    try:
        df_m_all = pd.read_sql_query("SELECT * FROM manutencoes", conn)
        if not df_m_all.empty and "valor" in df_m_all.columns:
            valores_limpos = pd.to_numeric(
                df_m_all["valor"].astype(str).str.replace('R$', '', regex=True).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
                errors='coerce'
            )
            custo_total_manut = float(valores_limpos.sum())
    except Exception:
        custo_total_manut = 0.0

    # Ocorrências pendentes
    try:
        qtd_pendencias = cursor.execute(
            "SELECT COUNT(*) FROM ocorrencias WHERE LOWER(status) IN ('pendente', 'aberto', 'em análise')"
        ).fetchone()[0]
    except Exception:
        qtd_pendencias = 0

    # Veículos completo
    try:
        df_veiculos_completo = pd.read_sql_query(
            "SELECT placa, marca, modelo, tipo_propriedade, locadora, inicio_contrato, fim_contrato, valor_mensal, status FROM veiculos WHERE status != 'Inativo'",
            conn,
        )
    except Exception:
        df_veiculos_completo = pd.DataFrame()

    # Manutenções recentes formatadas
    try:
        df_manutencoes = pd.read_sql_query(
            """
            SELECT m.id, v.placa, v.modelo, m.servico_realizado AS 'Serviço', m.valor AS 'Valor (R$)', m.status AS 'Status', m.data_conclusao AS 'Data'
            FROM manutencoes m 
            JOIN veiculos v ON m.veiculo_id = v.id 
            ORDER BY m.id DESC LIMIT 10
            """,
            conn,
        )
    except Exception:
        df_manutencoes = pd.DataFrame()

    conn.close()

    # Contratos a vencer
    qtd_contratos_atencao = 0
    if not df_veiculos_completo.empty:
        df_alug = df_veiculos_completo[
            df_veiculos_completo["tipo_propriedade"]
            .str.lower()
            .str.contains("alugado|terceirizado|locado", na=False)
        ]
        if not df_alug.empty:
            hoje = datetime.date.today()
            limite = hoje + datetime.timedelta(days=30)
            df_alug["fim_dt"] = pd.to_datetime(
                df_alug["fim_contrato"], errors="coerce"
            ).dt.date
            qtd_contratos_atencao = len(df_alug[df_alug["fim_dt"] <= limite])

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


def render_cards_veiculos(df_veiculos):
    """Renderiza a lista de veículos em formato de cards para telemóvel"""
    if df_veiculos.empty:
        st.info("Nenhum veículo encontrado.")
        return

    st.markdown("""
        <style>
        .veiculo-card {
            background-color: #111827;
            border: 1px solid #1f2937;
            border-left: 4px solid #3b82f6;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .veiculo-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }
        .veiculo-placa {
            font-size: 15px;
            font-weight: bold;
            color: #ffffff;
        }
        .veiculo-info {
            font-size: 12px;
            color: #9ca3af;
            margin-bottom: 2px;
        }
        .veiculo-info span {
            color: #f3f4f6;
            font-weight: 500;
        }
        </style>
    """, unsafe_allow_html=True)

    for index, row in df_veiculos.iterrows():
        placa = row.get('placa', 'N/A')
        marca = row.get('marca', '')
        modelo = row.get('modelo', '')
        tipo = row.get('tipo_propriedade', 'N/A')
        status = row.get('status', 'Ativo')
        locadora = row.get('locadora', '-')

        st.markdown(f"""
            <div class="veiculo-card">
                <div class="veiculo-header">
                    <span class="veiculo-placa">🚗 {placa}</span>
                    <span style="font-size: 11px; color: #34d399; font-weight: bold;">{status}</span>
                </div>
                <div class="veiculo-info">Modelo: <span>{marca} {modelo}</span></div>
                <div class="veiculo-info">Tipo: <span>{tipo}</span></div>
                <div class="veiculo-info">Locadora: <span>{locadora if locadora and str(locadora) != 'nan' else 'N/A'}</span></div>
            </div>
        """, unsafe_allow_html=True)


def render_dashboard(contar_registros_fn=None):
    st.title("📊 Painel Geral")

    # Carrega os dados reais rigorosamente com as consultas originais
    dados = carregar_dados_dashboard()

    # --- MÉTRICAS NATIVAS SEGURAS (Garante que os números aparecem corretos) ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚚 Frota Total", dados["veiculos"])
    c2.metric("🏢 Próprios", dados["proprios"])
    c3.metric("📋 Alugados", dados["alugados"])
    c4.metric("🛠️ Em Manutenção", dados["manut_andamento"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("💰 Custo Manutenções", f"R$ {dados['custo_total']:,.2f}")
    c6.metric("👨‍✈️ Motoristas", dados["motoristas"])
    c7.metric("⚠ Ocorrências", dados["pendencias"])
    c8.metric(
        "📄 Venc. Contratos",
        dados["contratos_atencao"],
        delta="Atenção" if dados["contratos_atencao"] > 0 else "OK",
        delta_color="inverse" if dados["contratos_atencao"] > 0 else "normal",
    )

    st.divider()

    # Abas originais intactas
    tab_contratos, tab_rodizio, tab_manut, tab_pendencias = st.tabs([
        "📄 Gestão de Contratos & Frota",
        "🚘 Rodízio Hoje",
        "🛠 Manutenções Recentes",
        "⚠ Ocorrências",
    ])

    with tab_contratos:
        df_v = dados["df_veiculos_completo"]
        if not df_v.empty:
            df_alugados = df_v[df_v["tipo_propriedade"].str.lower().str.contains("alugado|terceirizado|locado", na=False)]
            df_proprios = df_v[df_v["tipo_propriedade"].str.lower().str.contains("próprio|proprio", na=False)]

            sub1, sub2 = st.tabs(["📋 Alugados / Terceirizados", "🏢 Próprios"])
            with sub1:
                if not df_alugados.empty:
                    render_cards_veiculos(df_alugados)
                else:
                    st.info("Nenhum veículo alugado encontrado.")
            with sub2:
                if not df_proprios.empty:
                    render_cards_veiculos(df_proprios)
                else:
                    st.info("Nenhum veículo próprio encontrado.")
        else:
            st.info("Nenhum veículo registado.")

    with tab_rodizio:
        st.markdown("##### Consulta de Rodízio (SP)")
        hoje_idx = datetime.datetime.now().weekday()
        regras = {0: "Placas 1 e 2", 1: "Placas 3 e 4", 2: "Placas 5 e 6", 3: "Placas 7 e 8", 4: "Placas 9 e 0"}
        if hoje_idx < 5:
            st.warning(f"🚫 Restrição hoje: {regras.get(hoje_idx)}")
        else:
            st.success("✅ Sem restrição no fim de semana.")

    with tab_manut:
        if not dados["df_manutencoes"].empty:
            st.dataframe(dados["df_manutencoes"], use_container_width=True, hide_index=True)
        else:
            st.info("Sem manutenções recentes.")

    with tab_pendencias:
        try:
            conn = get_connection()
            df_oc = pd.read_sql_query("SELECT o.id, v.placa, o.descricao, o.status FROM ocorrencias o JOIN veiculos v ON o.veiculo_id = v.id WHERE LOWER(o.status) IN ('pendente', 'aberto')", conn)
            conn.close()
            if not df_oc.empty:
                st.dataframe(df_oc, use_container_width=True, hide_index=True)
            else:
                st.success("Nenhuma ocorrência pendente!")
        except Exception:
            st.info("Sem ocorrências.")
