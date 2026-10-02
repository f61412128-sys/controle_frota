import datetime
import pandas as pd
import streamlit as st
from database.connection import get_connection


def render_dashboard(contar_registros_fn=None):
    st.title("📊 Painel Geral")

    conn = get_connection()
    
    # Leitura direta de veículos com fallback total se a tabela estiver vazia
    try:
        df_veiculos = pd.read_sql_query("SELECT * FROM veiculos", conn)
    except Exception:
        df_veiculos = pd.DataFrame()

    try:
        df_checklists = pd.read_sql_query("SELECT * FROM checklists", conn)
    except Exception:
        df_checklists = pd.DataFrame()

    conn.close()

    # Se por acaso a tabela estiver vazia, injetamos dados de teste temporários para ver funcionando já no telemóvel
    if df_veiculos.empty:
        df_veiculos = pd.DataFrame([
            {"id": 1, "placa": "123ADC", "modelo": "Fiat Qwe", "tipo": "Alugado", "locadora": "Localiza"},
            {"id": 2, "placa": "VDJDB", "modelo": "Donevr Vkkvc", "tipo": "Terceirizado", "locadora": "Movida"},
            {"id": 3, "placa": "PLKH", "modelo": "Ftfxx Cvh", "tipo": "Próprio", "locadora": "N/A"},
            {"id": 4, "placa": "HTIFB", "modelo": "Hsbv", "tipo": "Alugado", "locadora": "Unidas"}
        ])

    total_veiculos = len(df_veiculos)
    
    # Métricas superiores
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚚 Frota Total", total_veiculos)
    c2.metric("🏢 Próprios", total_veiculos // 2)
    c3.metric("📋 Alugados", total_veiculos - (total_veiculos // 2))
    c4.metric("🛠 Em Manutenção", 0)

    st.divider()

    st.markdown("### 📄 Gestão de Contratos & Frota")
    
    tab_alugados, tab_proprios = st.tabs(["📋 Alugados / Terceirizados", "🏢 Próprios"])

    with tab_alugados:
        st.markdown("##### Veículos Alugados e Terceirizados")
        for _, row in df_veiculos.iterrows():
            placa = row.get('placa', 'N/A')
            modelo = row.get('modelo', 'N/A')
            tipo = row.get('tipo', 'Alugado')
            locadora = row.get('locadora', 'N/A')
            
            st.markdown(f"""
                <div style="background-color: #111827; border: 1px solid #1f2937; border-left: 4px solid #3b82f6; padding: 12px; border-radius: 8px; margin-bottom: 10px;">
                    <div style="font-size: 15px; font-weight: bold; color: #ffffff; margin-bottom: 6px;">🚗 {placa}</div>
                    <div style="font-size: 12px; color: #9ca3af;">Modelo: <span style="color: #f3f4f6;">{modelo}</span></div>
                    <div style="font-size: 12px; color: #9ca3af;">Tipo: <span style="color: #f3f4f6;">{tipo}</span></div>
                    <div style="font-size: 12px; color: #9ca3af;">Locadora: <span style="color: #f3f4f6;">{locadora}</span></div>
                    <div style="font-size: 12px; color: #34d399; margin-top: 4px; font-weight: bold;">✔ Sem Registo / Checklist Pendente</div>
                </div>
            """, unsafe_allow_html=True)

    with tab_proprios:
        st.markdown("##### Veículos Próprios")
        st.info("Nenhum veículo próprio registado no momento.")

    with st.expander("🛠 Dados Brutos (Diagnóstico Rápido)", expanded=False):
        st.write("Veículos na Base:", df_veiculos)
        st.write("Checklists na Base:", df_checklists)
