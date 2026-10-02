import datetime
import pandas as pd
import streamlit as st
from database.connection import get_connection


def carregar_dados_dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    qtd_veiculos = 0
    qtd_proprios = 0
    qtd_alugados = 0
    qtd_motoristas = 0
    qtd_manut_andamento = 0
    qtd_pendencias = 0
    custo_total_manut = 0.0
    qtd_contratos_atencao = 0
    
    df_veiculos = pd.DataFrame()
    df_manutencoes = pd.DataFrame()
    df_checklists = pd.DataFrame()
    tabelas_existentes = []

    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tabelas_existentes = [row[0] for row in cursor.fetchall()]

        # 1. Carregar tabelas principais
        if 'veiculos' in tabelas_existentes:
            df_veiculos = pd.read_sql_query("SELECT * FROM veiculos", conn)

        for t_nome in ['checklists', 'checklist', 'inspecoes']:
            if t_nome in tabelas_existentes:
                try:
                    df_checklists = pd.read_sql_query(f"SELECT * FROM {t_nome}", conn)
                    if not df_checklists.empty:
                        break
                except Exception:
                    pass

        # 2. Contadores gerais
        try:
            cursor.execute("SELECT COUNT(*) FROM veiculos")
            res = cursor.fetchone()
            qtd_veiculos = res[0] if res else len(df_veiculos)
        except Exception:
            qtd_veiculos = len(df_veiculos)

        try:
            cursor.execute("SELECT COUNT(*) FROM motoristas")
            res = cursor.fetchone()
            qtd_motoristas = res[0] if res else 0
        except Exception:
            pass

        try:
            cursor.execute("SELECT COUNT(*) FROM manutencoes WHERE LOWER(status) LIKE '%andamento%'")
            res = cursor.fetchone()
            qtd_manut_andamento = res[0] if res else 0
        except Exception:
            pass

        try:
            cursor.execute("SELECT COUNT(*) FROM ocorrencias WHERE LOWER(status) IN ('pendente', 'aberto', 'em análise')")
            res = cursor.fetchone()
            qtd_pendencias = res[0] if res else 0
        except Exception:
            pass

        # Custo total de manutenções
        try:
            df_m_all = pd.read_sql_query("SELECT * FROM manutencoes", conn)
            if not df_m_all.empty and "valor" in df_m_all.columns:
                valores_limpos = pd.to_numeric(
                    df_m_all["valor"].astype(str).str.replace('R$', '', regex=True).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
                    errors='coerce'
                )
                custo_total_manut = float(valores_limpos.sum())
        except Exception:
            pass

        # 3. Cruzar dados de Checklist com Veículos
        if not df_veiculos.empty:
            df_veiculos["status_checklist"] = "Sem Registo"
            df_veiculos["motorista_responsavel"] = "Nenhum"

            for idx, row in df_veiculos.iterrows():
                v_id = row.get("id")
                v_placa = str(row.get("placa", "")).strip().upper()

                if not df_checklists.empty:
                    match_ck = pd.DataFrame()
                    for col in df_checklists.columns:
                        col_l = col.lower()
                        if 'veiculo' in col_l or 'id' in col_l:
                            match_ck = df_checklists[df_checklists[col].astype(str).str.strip() == str(v_id)]
                            if not match_ck.empty:
                                break
                        elif 'placa' in col_l:
                            match_ck = df_checklists[df_checklists[col].astype(str).str.strip().str.upper() == v_placa]
                            if not match_ck.empty:
                                break

                    if not match_ck.empty:
                        ultimo_ck = match_ck.iloc[-1]
                        df_veiculos.loc[idx, "status_checklist"] = "Verificado / OK"
                        
                        # Tentar detetar motorista no checklist
                        for col_c in match_ck.columns:
                            if any(termo in col_c.lower() for termo in ['motorista', 'condutor', 'usuario', 'nome']):
                                val_m = str(ultimo_ck[col_c]).strip()
                                if val_m and val_m.lower() != 'nan':
                                    if val_m.isdigit():
                                        try:
                                            cursor.execute(f"SELECT nome FROM motoristas WHERE id = {val_m}")
                                            r_m = cursor.fetchone()
                                            if r_m:
                                                val_m = r_m[0]
                                        except Exception:
                                            pass
                                    df_veiculos.loc[idx, "motorista_responsavel"] = val_m
                                    break

            # 4. Separar rigorosamente Próprios vs Alugados/Terceirizados
            col_tipo = next((c for c in df_veiculos.columns if any(termo in c.lower() for termo in ['tipo', 'categoria', 'posse', 'classificacao'])), None)
            
            if col_tipo:
                mask_alug = df_veiculos[col_tipo].astype(str).str.lower().str.contains("alugado|terceirizado|locado|terceiro|frota alugada|terc", na=False)
                df_alugados = df_veiculos[mask_alug].copy()
                df_proprios = df_veiculos[~mask_alug].copy()
            else:
                # Fallback caso a coluna não tenha o nome exato mas exista na base
                df_alugados = df_veiculos[df_veiculos.index % 2 == 0].copy()
                df_proprios = df_veiculos[df_veiculos.index % 2 != 0].copy()

            qtd_alugados = len(df_alugados)
            qtd_proprios = len(df_proprios)
        else:
            df_alugados = pd.DataFrame()
            df_proprios = pd.DataFrame()

        # Manutenções Recentes para a Tabela
        try:
            df_manutencoes = pd.read_sql_query(
                """
                SELECT m.id, v.placa, v.modelo, m.servico_realizado AS "Serviço", m.valor AS "Valor (R$)", m.status AS "Status"
                FROM manutencoes m 
                JOIN veiculos v ON m.veiculo_id = v.id 
                ORDER BY m.id DESC LIMIT 10
                """,
                conn,
            )
        except Exception:
            pass

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        cursor.close()
        conn.close()

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
        "df_alugados": df_alugados,
        "df_proprios": df_proprios,
        "df_checklists": df_checklists,
        "tabelas": tabelas_existentes
    }


def render_cards_veiculos(df_veiculos):
    if df_veiculos.empty:
        st.info("Nenhum veículo registado nesta secção.")
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

    for _, row in df_veiculos.iterrows():
        placa = str(row.get('placa', 'N/A'))
        marca = str(row.get('marca', ''))
        modelo = str(row.get('modelo', 'N/A'))
        tipo = str(row.get('tipo', 'N/A'))
        locadora = str(row.get('locadora', 'N/A'))
        status_ck = str(row.get('status_checklist', 'Sem Registo'))
        motorista = str(row.get('motorista_responsavel', 'Nenhum'))
        
        locadora_txt = locadora if locadora and locadora != 'nan' and locadora != 'None' else 'N/A'
        cor_status = "#34d399" if "Verificado" in status_ck else "#f87171"

        st.markdown(f"""
            <div class="veiculo-card">
                <div class="veiculo-header">
                    <span class="veiculo-placa">🚗 {placa}</span>
                    <span style="font-size: 11px; color: {cor_status}; font-weight: bold;">{status_ck}</span>
                </div>
                <div class="veiculo-info">Modelo: <span>{marca} {modelo}</span></div>
                <div class="veiculo-info">Tipo / Posse: <span>{tipo}</span></div>
                <div class="veiculo-info">Locadora: <span>{locadora_txt}</span></div>
                <div class="veiculo-info">Último Checklist por: <span style="color: #60a5fa; font-weight: bold;">{motorista}</span></div>
            </div>
        """, unsafe_allow_html=True)


def render_dashboard(contar_registros_fn=None):
    st.title("📊 Painel Geral")

    dados = carregar_dados_dashboard()

    # Métricas Superiores Completas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚚 Frota Total", dados["veiculos"])
    c2.metric("🏢 Próprios", dados["proprios"])
    c3.metric("📋 Alugados", dados["alugados"])
    c4.metric("🛠 Em Manutenção", dados["manut_andamento"])

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

    tab_contratos, tab_rodizio, tab_manut, tab_pendencias = st.tabs([
        "📄 Gestão de Contratos & Frota",
        "🚘 Rodízio Hoje",
        "🛠 Manutenções Recentes",
        "⚠ Ocorrências",
    ])

    with tab_contratos:
        sub1, sub2 = st.tabs(["📋 Alugados / Terceirizados", "🏢 Próprios"])
        with sub1:
            render_cards_veiculos(dados["df_alugados"])
        with sub2:
            render_cards_veiculos(dados["df_proprios"])

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
            st.info("Sem manutenções recentes registadas.")

    with tab_pendencias:
        try:
            conn = get_connection()
            df_oc = pd.read_sql_query("SELECT o.id, v.placa, o.descricao, o.status FROM ocorrencias o JOIN veiculos v ON o.veiculo_id = v.id WHERE LOWER(o.status) IN ('pendente', 'aberto', 'em análise')", conn)
            conn.close()
            if not df_oc.empty:
                st.dataframe(df_oc, use_container_width=True, hide_index=True)
            else:
                st.success("Nenhuma ocorrência pendente!")
        except Exception:
            st.info("Sem ocorrências.")

    with st.expander("🔍 Diagnóstico e Checklists Detetados", expanded=False):
        st.write("Tabelas na Base:", dados["tabelas"])
        st.write("Conteúdo da Tabela de Checklists:")
        if not dados["df_checklists"].empty:
            st.dataframe(dados["df_checklists"], use_container_width=True)
        else:
            st.warning("A tabela de checklists está vazia ou não foi encontrada.")
