import datetime
import os
import pandas as pd
import streamlit as st
from database.connection import get_connection


def render_dashboard(contar_registros_fn=None):
    st.title("📊 Painel Geral (v3.0 - Forçado)")

    # 1. Ligação segura à base de dados
    try:
        conn = get_connection()
    except Exception as e:
        st.error(f"Erro ao ligar à base de dados: {e}")
        return

    # 2. Leitura de dados com tratamento de tabelas vazias ou inexistentes
    try:
        df_veiculos = pd.read_sql_query("SELECT * FROM veiculos", conn)
    except Exception:
        df_veiculos = pd.DataFrame()

    try:
        df_manutencoes = pd.read_sql_query("SELECT * FROM manutencoes", conn)
    except Exception:
        df_manutencoes = pd.DataFrame()

    try:
        df_motoristas = pd.read_sql_query("SELECT * FROM motoristas", conn)
    except Exception:
        df_motoristas = pd.DataFrame()

    try:
        df_checklists = pd.read_sql_query("SELECT * FROM checklists", conn)
    except Exception:
        df_checklists = pd.DataFrame()

    conn.close()

    # 3. Cálculo do Custo de Manutenções
    custo_total_manut = 0.0
    if not df_manutencoes.empty:
        for col_val in ['valor', 'custo', 'preco', 'valor_total']:
            if col_val in df_manutencoes.columns:
                try:
                    valores_limpos = pd.to_numeric(
                        df_manutencoes[col_val].astype(str)
                        .str.replace('R$', '', regex=True)
                        .str.replace('.', '', regex=False)
                        .str.replace(',', '.', regex=False),
                        errors='coerce'
                    )
                    custo_total_manut = float(valores_limpos.sum())
                    break
                except Exception:
                    pass

    # 4. Filtragem robusta baseada em tipo_propriedade ou tipo
    df_alugados = pd.DataFrame()
    df_proprios = pd.DataFrame()

    if not df_veiculos.empty:
        # Descobrir qual coluna indica o tipo
        col_alvo = None
        for c in ['tipo_propriedade', 'tipo', 'posse', 'categoria']:
            if c in df_veiculos.columns:
                col_alvo = c
                break

        if col_alvo:
            # Tudo o que contiver alugado ou terceirizado
            mask_alug = df_veiculos[col_alvo].astype(str).str.lower().str.contains("alugado|terceirizado|locado|terceiro", na=False)
            df_alugados = df_veiculos[mask_alug].copy()
            
            # O resto ou o que for próprio
            mask_prop = df_veiculos[col_alvo].astype(str).str.lower().str.contains("próprio|proprio", na=False)
            df_proprios = df_veiculos[mask_prop].copy()
            
            # Se a máscara própria vier vazia mas houver registos que não são alugados
            if df_proprios.empty:
                df_proprios = df_veiculos[~mask_alug].copy()
        else:
            df_proprios = df_veiculos.copy()

    total_veiculos = len(df_veiculos)
    total_proprios = len(df_proprios)
    total_alugados = len(df_alugados)
    total_motoristas = len(df_motoristas) if not df_motoristas.empty else 0
    total_manut = len(df_manutencoes)

    # 5. Métricas Superiores
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚚 Frota Total", total_veiculos)
    c2.metric("🏢 Próprios", total_proprios)
    c3.metric("📋 Alugados", total_alugados)
    c4.metric("🛠 Em Manutenção", total_manut)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("💰 Custo Manutenções", f"R$ {custo_total_manut:,.2f}")
    c6.metric("👨‍✈️ Motoristas", total_motoristas)
    c7.metric("⚠ Ocorrências", 0)
    c8.metric("📄 Venc. Contratos", 0, delta="OK")

    st.divider()

    # 6. Abas Principais
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
                    tipo = row.get('tipo_propriedade', row.get('tipo', 'Alugado'))
                    
                    with st.container(border=True):
                        st.markdown(f"**🚗 Placa:** {placa}")
                        st.write(f"**Modelo:** {modelo}")
                        st.write(f"**Tipo:** {tipo}")
            else:
                st.info("Nenhum veículo alugado ou terceirizado registado na base de dados.")

        with sub_prop:
            st.markdown("##### Veículos Próprios")
            if not df_proprios.empty:
                for _, row in df_proprios.iterrows():
                    placa = row.get('placa', 'N/A')
                    modelo = row.get('modelo', 'N/A')
                    tipo = row.get('tipo_propriedade', row.get('tipo', 'Próprio'))
                    
                    with st.container(border=True):
                        st.markdown(f"**🏢 Placa:** {placa}")
                        st.write(f"**Modelo:** {modelo}")
                        st.write(f"**Tipo:** {tipo}")
            else:
                st.info("Nenhum veículo próprio registado na base de dados.")

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

    # 7. Diagnóstico em aberto para validação imediata
    with st.expander("🔍 Diagnóstico Completo da Base de Dados", expanded=True):
        st.write(f"Total de registos em `veiculos`: {len(df_veiculos)}")
        if not df_veiculos.empty:
            st.dataframe(df_veiculos, use_container_width=True)
        else:
            st.warning("A tabela `veiculos` está completamente vazia no SQLite.")
            
        st.write(f"Total de registos em `manutencoes`: {len(df_manutencoes)}")
        if not df_manutencoes.empty:
            st.dataframe(df_manutencoes, use_container_width=True)
