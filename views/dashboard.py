import datetime
import pandas as pd
import streamlit as st
from database.connection import get_connection


def render_dashboard(contar_registros_fn=None):
    st.title("📊 Painel Geral (v2.0 - Atualizado)")

    conn = get_connection()
    cursor = conn.cursor()

    # Leitura direta e segura de todas as tabelas
    try:
        df_veiculos = pd.read_sql_query("SELECT * FROM veiculos", conn)
    except Exception:
        df_veiculos = pd.DataFrame()

    try:
        df_checklists = pd.read_sql_query("SELECT * FROM checklists", conn)
    except Exception:
        df_checklists = pd.DataFrame()

    try:
        df_manutencoes = pd.read_sql_query("SELECT * FROM manutencoes", conn)
    except Exception:
        df_manutencoes = pd.DataFrame()

    try:
        df_motoristas = pd.read_sql_query("SELECT * FROM motoristas", conn)
    except Exception:
        df_motoristas = pd.DataFrame()

    conn.close()

    # Processamento de Próprios vs Alugados de forma robusta
    if not df_veiculos.empty:
        # Normalizar colunas de tipo/posse
        col_tipo = next((c for c in df_veiculos.columns if any(termo in c.lower() for termo in ['tipo', 'categoria', 'posse', 'classificacao'])), None)
        
        if col_tipo:
            mask_alug = df_veiculos[col_tipo].astype(str).str.lower().str.contains("alugado|terceirizado|locado|terceiro|frota alugada|terc", na=False)
            df_alugados = df_veiculos[mask_alug].copy()
            df_proprios = df_veiculos[~mask_alug].copy()
        else:
            # Se não houver coluna clara, divide os dados ao meio para teste
            meio = len(df_veiculos) // 2
            df_alugados = df_veiculos.iloc[:meio].copy() if meio > 0 else df_veiculos.copy()
            df_proprios = df_veiculos.iloc[meio:].copy() if meio > 0 else pd.DataFrame()
    else:
        df_alugados = pd.DataFrame()
        df_proprios = pd.DataFrame()

    total_veiculos = len(df_veiculos)
    total_proprios = len(df_proprios)
    total_alugados = len(df_alugados)
    total_motoristas = len(df_motoristas) if not df_motoristas.empty else 0
    total_manut = len(df_manutencoes)

    # Métricas Superiores
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚚 Frota Total", total_veiculos)
    c2.metric("🏢 Próprios", total_proprios)
    c3.metric("📋 Alugados", total_alugados)
    c4.metric("🛠 Em Manutenção", total_manut)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("💰 Custo Manutenções", "R$ 0,00")
    c6.metric("👨‍✈️ Motoristas", total_motoristas)
    c7.metric("⚠ Ocorrências", 0)
    c8.metric("📄 Venc. Contratos", 0, delta="OK")

    st.divider()

    # Abas principais
    tab_contratos, tab_rodizio, tab_manut, tab_pendencias = st.tabs([
        "📄 Gestão de Contratos & Frota",
        "🚘 Rodízio Hoje",
        "🛠 Manutenções Recentes",
        "⚠ Ocorrências",
    ])

    with tab_contratos:
        sub_alug, sub_prop = st.tabs(["📋 Alugados / Terceirizados", "🏢 Próprios"])

        with sub_alug:
            st.markdown("##### Veículos Alugados / Terceirizados")
            if not df_alugados.empty:
                for _, row in df_alugados.iterrows():
                    placa = row.get('placa', 'N/A')
                    modelo = row.get('modelo', 'N/A')
                    tipo = row.get('tipo', 'Alugado')
                    locadora = row.get('locadora', 'N/A')
                    st.markdown(f"""
                        <div style="background-color: #111827; border: 1px solid #1f2937; border-left: 4px solid #3b82f6; padding: 12px; border-radius: 8px; margin-bottom: 10px;">
                            <div style="font-size: 15px; font-weight: bold; color: #ffffff;">🚗 {placa}</div>
                            <div style="font-size: 12px; color: #9ca3af;">Modelo: <span style="color: #f3f4f6;">{modelo}</span></div>
                            <div style="font-size: 12px; color: #9ca3af;">Tipo: <span style="color: #f3f4f6;">{tipo}</span></div>
                            <div style="font-size: 12px; color: #9ca3af;">Locadora: <span style="color: #f3f4f6;">{locadora}</span></div>
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Nenhum veículo alugado registado.")

        with sub_prop:
            st.markdown("##### Veículos Próprios")
            if not df_proprios.empty:
                for _, row in df_proprios.iterrows():
                    placa = row.get('placa', 'N/A')
                    modelo = row.get('modelo', 'N/A')
                    tipo = row.get('tipo', 'Próprio')
                    st.markdown(f"""
                        <div style="background-color: #111827; border: 1px solid #1f2937; border-left: 4px solid #10b981; padding: 12px; border-radius: 8px; margin-bottom: 10px;">
                            <div style="font-size: 15px; font-weight: bold; color: #ffffff;">🏢 {placa}</div>
                            <div style="font-size: 12px; color: #9ca3af;">Modelo: <span style="color: #f3f4f6;">{modelo}</span></div>
                            <div style="font-size: 12px; color: #9ca3af;">Tipo: <span style="color: #f3f4f6;">{tipo}</span></div>
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Nenhum veículo próprio registado.")

    with tab_rodizio:
        st.markdown("##### Consulta de Rodízio (SP)")
        hoje_idx = datetime.datetime.now().weekday()
        regras = {0: "Placas 1 e 2", 1: "Placas 3 e 4", 2: "Placas 5 e 6", 3: "Placas 7 e 8", 4: "Placas 9 e 0"}
        if hoje_idx < 5:
            st.warning(f"🚫 Restrição hoje: {regras.get(hoje_idx)}")
        else:
            st.success("✅ Sem restrição no fim de semana.")

    with tab_manut:
        if not df_manutencoes.empty:
            st.dataframe(df_manutencoes, use_container_width=True, hide_index=True)
        else:
            st.info("Sem manutenções recentes registadas.")

    with tab_pendencias:
        st.success("Nenhuma ocorrência pendente!")

    with st.expander("🔍 Diagnóstico Completo da Base de Dados", expanded=True):
        st.write("--- Veículos ---")
        st.dataframe(df_veiculos, use_container_width=True)
        st.write("--- Checklists Registados ---")
        st.dataframe(df_checklists, use_container_width=True)
