import datetime
import sqlite3
import pandas as pd
import streamlit as st
from database.connection import get_connection


def carregar_dados_dashboard():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Contadores de veículos
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

    # Manutenções e Custo Total (Forçando a coluna 'valor')
    qtd_manut_andamento = 0
    custo_total_manut = 0.0
    try:
        qtd_manut_andamento = cursor.execute(
            "SELECT COUNT(*) FROM manutencoes WHERE LOWER(status) LIKE '%andamento%'"
        ).fetchone()[0]
    except Exception:
        pass

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
    """Renderiza a lista de veículos em formato de cards modernos (Mobile-First)"""
    if df_veiculos.empty:
        st.info("Nenhum veículo registado para exibir.")
        return

    # Estilo CSS customizado para os cartões de veículos (Tema Dark NOSSOAR)
    st.markdown("""
        <style>
        .veiculo-card {
            background-color: #111827;
            border: 1px solid #1f2937;
            border-left: 4px solid #3b82f6;
            padding: 14px;
            border-radius: 10px;
            margin-bottom: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        .veiculo-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .veiculo-placa {
            font-size: 16px;
            font-weight: bold;
            color: #ffffff;
            letter-spacing: 1px;
        }
        .veiculo-status-ativo {
            background-color: #064e3b;
            color: #34d399;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: bold;
        }
        .veiculo-status-manu {
            background-color: #78350f;
            color: #fbbf24;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: bold;
        }
        .veiculo-info {
            font-size: 13px;
            color: #9ca3af;
            margin-bottom: 4px;
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

        badge_class = "veiculo-status-ativo" if str(status).lower() == "ativo" else "veiculo-status-manu"

        st.markdown(f"""
            <div class="veiculo-card">
                <div class="veiculo-header">
                    <span class="veiculo-placa">🚗 {placa}</span>
                    <span class="{badge_class}">{status}</span>
                </div>
                <div class="veiculo-info">Modelo: <span>{marca} {modelo}</span></div>
                <div class="veiculo-info">Tipo: <span>{tipo}</span></div>
                <div class="veiculo-info">Locadora: <span>{locadora if locadora and str(locadora) != 'nan' else 'N/A'}</span></div>
            </div>
        """, unsafe_allow_html=True)

        if st.button(f"🔍 Ver detalhes de {placa}", key=f"btn_detalhe_{placa}_{index}"):
            st.toast(f"A abrir detalhes do veículo {placa}...")


def render_dashboard(contar_registros_fn=None):
    # Injeção de CSS global para o Painel Geral
    st.markdown("""
        <style>
        .welcome-banner {
            background: linear-gradient(90deg, #1e1b4b 0%, #172554 100%);
            border: 1px solid #1e3a8a;
            padding: 16px 20px;
            border-radius: 12px;
            color: #ffffff;
            margin-bottom: 20px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
        .welcome-title {
            font-size: 20px;
            font-weight: bold;
            color: #60a5fa;
        }
        .welcome-subtitle {
            font-size: 13px;
            color: #94a3b8;
            margin-top: 2px;
        }
        .metric-card {
            background-color: #111827;
            border: 1px solid #1f2937;
            padding: 14px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            margin-bottom: 10px;
        }
        .metric-label {
            font-size: 11px;
            color: #9ca3af;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .metric-value {
            font-size: 20px;
            font-weight: bold;
            color: #ffffff;
            margin-top: 4px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="welcome-banner">
            <div class="welcome-title">Olá, Administrador!</div>
            <div class="welcome-subtitle">Painel de controlo NOSSOAR.</div>
        </div>
    """, unsafe_allow_html=True)

    dados = carregar_dados_dashboard()

    # --- MÉTRICAS SUPERIORES ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">🚚 Frota</div><div class="metric-value">{dados["veiculos"]}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">🚙 Próprios</div><div class="metric-value">{dados["proprios"]}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">🏢 Alugados</div><div class="metric-value">{dados["alugados"]}</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">🛠️ Manut.</div><div class="metric-value" style="color: #60a5fa;">{dados["manut_andamento"]}</div></div>', unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(f'<div class="metric-card"><div class="metric-label">💰 Custo</div><div class="metric-value" style="font-size: 14px; color: #34d399;">R$ {dados['custo_total']:,.2f}</div></div>', unsafe_allow_html=True)
    with c6:
        st.markdown(f'<div class="metric-card"><div class="metric-label">👨‍‍✈️ Motoristas</div><div class="metric-value">{dados["motoristas"]}</div></div>', unsafe_allow_html=True)
    with c7:
        st.markdown(f'<div class="metric-card"><div class="metric-label">⚠ Ocorrências</div><div class="metric-value" style="color: #f87171;">{dados["pendencias"]}</div></div>', unsafe_allow_html=True)
    with c8:
        cor_contrato = "#fbbf24" if dados["contratos_atencao"] > 0 else "#34d399"
        status_txt = f"Atenção ({dados['contratos_atencao']})" if dados["contratos_atencao"] > 0 else "OK"
        st.markdown(f'<div class="metric-card"><div class="metric-label">📄 Contratos</div><div class="metric-value" style="font-size: 14px; color: {cor_contrato};">{status_txt}</div></div>', unsafe_allow_html=True)

    st.divider()

    # Abas da Aplicação
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
                    # APLICADO O NOVO SISTEMA DE CARDS TOCÁVEIS AQUI!
                    render_cards_veiculos(df_alugados)
                else:
                    st.info("Nenhum veículo alugado encontrado.")
            with sub2:
                if not df_proprios.empty:
                    # APLICADO O NOVO SISTEMA DE CARDS TOCÁVEIS AQUI!
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
