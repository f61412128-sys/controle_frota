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
    df_veiculos_completo = pd.DataFrame()
    df_manutencoes = pd.DataFrame()
    df_debug_checklists = pd.DataFrame()

    try:
        # 1. Contadores gerais de forma segura
        try:
            cursor.execute("SELECT COUNT(*) FROM veiculos")
            res = cursor.fetchone()
            qtd_veiculos = res[0] if res else 0
        except Exception:
            pass

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

        # Custo de manutenções
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

        # 2. Carregar veículos
        try:
            df_veiculos_completo = pd.read_sql_query("SELECT * FROM veiculos", conn)
        except Exception:
            df_veiculos_completo = pd.DataFrame()

        # Separar contadores de próprios e alugados com base no DataFrame carregado (mais seguro)
        if not df_veiculos_completo.empty:
            col_tipo = next((c for c in df_veiculos_completo.columns if 'tipo' in c.lower()), None)
            if col_tipo:
                df_temp_alug = df_veiculos_completo[df_veiculos_completo[col_tipo].astype(str).str.lower().str.contains("alugado|terceirizado|locado", na=False)]
                df_temp_prop = df_veiculos_completo[df_veiculos_completo[col_tipo].astype(str).str.lower().str.contains("próprio|proprio", na=False)]
                qtd_alugados = len(df_temp_alug)
                qtd_proprios = len(df_temp_prop)
            else:
                qtd_proprios = len(df_veiculos_completo)

        # 3. Capturar checklists para debug
        try:
            df_debug_checklists = pd.read_sql_query("SELECT * FROM checklists ORDER BY id DESC LIMIT 5", conn)
        except Exception:
            pass

        # Enriquecer cada veículo com status de checklist e motorista responsável
        if not df_veiculos_completo.empty:
            df_veiculos_completo["status_checklist"] = "Disponível"
            df_veiculos_completo["motorista_responsavel"] = "Nenhum / Na Empresa"

            for idx, row in df_veiculos_completo.iterrows():
                v_id = row.get("id")
                placa = row.get("placa")
                try:
                    q_single = f"SELECT * FROM checklists WHERE veiculo_id = {v_id} OR id_veiculo = {v_id} OR placa = '{placa}' ORDER BY id DESC LIMIT 1"
                    df_c = pd.read_sql_query(q_single, conn)
                    if not df_c.empty:
                        c_row = df_c.iloc[0]
                        for col_s in ["status", "status_veiculo", "condicao", "situacao"]:
                            if col_s in df_c.columns and pd.notna(c_row[col_s]):
                                df_veiculos_completo.loc[idx, "status_checklist"] = str(c_row[col_s])
                                break
                        
                        mot_nome = None
                        for col_m in ["motorista", "nome_motorista", "condutor", "usuario", "responsavel"]:
                            if col_m in df_c.columns and pd.notna(c_row[col_m]):
                                mot_nome = str(c_row[col_m])
                                break
                        
                        if not mot_nome:
                            for col_m_id in ["motorista_id", "id_motorista"]:
                                if col_m_id in df_c.columns and pd.notna(c_row[col_m_id]):
                                    m_id = c_row[col_m_id]
                                    cursor.execute(f"SELECT nome FROM motoristas WHERE id = {m_id}")
                                    res_m = cursor.fetchone()
                                    if res_m:
                                        mot_nome = res_m[0]
                                    break

                        if mot_nome:
                            df_veiculos_completo.loc[idx, "motorista_responsavel"] = mot_nome
                except Exception:
                    pass

        # 4. Manutenções recentes
        try:
            df_manutencoes = pd.read_sql_query(
                """
                SELECT m.id, v.placa, v.modelo, m.servico_realizado AS "Serviço", m.valor AS "Valor (R$)", m.status AS "Status", m.data_conclusao AS "Data"
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

    # Contratos a vencer (últimos 30 dias)
    if not df_veiculos_completo.empty:
        try:
            col_fim = next((c for c in df_veiculos_completo.columns if 'fim' in c.lower() or 'vencimento' in c.lower() or 'contrato' in c.lower()), None)
            col_tipo = next((c for c in df_veiculos_completo.columns if 'tipo' in c.lower()), None)
            
            if col_tipo and col_fim:
                df_alug = df_veiculos_completo[
                    df_veiculos_completo[col_tipo].astype(str).str.lower().str.contains("alugado|terceirizado|locado", na=False)
                ]
                if not df_alug.empty:
                    hoje = datetime.date.today()
                    limite = hoje + datetime.timedelta(days=30)
                    df_alug["fim_dt"] = pd.to_datetime(df_alug[col_fim], errors="coerce").dt.date
                    qtd_contratos_atencao = len(df_alug[(df_alug["fim_dt"] >= hoje) & (df_alug["fim_dt"] <= limite)])
        except Exception:
            pass

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
        "df_debug_checklists": df_debug_checklists,
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

    for index, row in df_veiculos.iterrows():
        placa = str(row.get('placa') or row.get('Placa') or 'N/A')
        marca = str(row.get('marca') or row.get('Marca') or '')
        modelo = str(row.get('modelo') or row.get('Modelo') or '')
        
        tipo = 'N/A'
        for col in row.index:
            if 'tipo' in col.lower():
                tipo = str(row[col])
                break

        locadora = str(row.get('locadora') or row.get('Locadora') or '-')
        
        texto_status = str(row.get('status_checklist', 'Disponível'))
        motorista_txt = str(row.get('motorista_responsavel', 'Nenhum / Na Empresa'))
        locadora_txt = locadora if locadora and locadora != 'nan' and locadora != 'None' else 'N/A'

        st.markdown(f"""
            <div class="veiculo-card">
                <div class="veiculo-header">
                    <span class="veiculo-placa">🚗 {placa}</span>
                    <span style="font-size: 11px; color: #34d399; font-weight: bold;">{texto_status}</span>
                </div>
                <div class="veiculo-info">Modelo: <span>{marca} {modelo}</span></div>
                <div class="veiculo-info">Tipo: <span>{tipo}</span></div>
                <div class="veiculo-info">Locadora: <span>{locadora_txt}</span></div>
                <div class="veiculo-info">Responsável / Último Checklist: <span style="color: #60a5fa;">{motorista_txt}</span></div>
            </div>
        """, unsafe_allow_html=True)


def render_dashboard(contar_registros_fn=None):
    st.title("📊 Painel Geral")

    dados = carregar_dados_dashboard()

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
        df_v = dados["df_veiculos_completo"]
        if not df_v.empty:
            df_alugados = pd.DataFrame()
            df_proprios = pd.DataFrame()
            
            try:
                col_tipo = next((c for c in df_v.columns if 'tipo' in c.lower()), None)
                if col_tipo:
                    df_alugados = df_v[df_v[col_tipo].astype(str).str.lower().str.contains("alugado|terceirizado|locado", na=False)]
                    df_proprios = df_v[df_v[col_tipo].astype(str).str.lower().str.contains("próprio|proprio", na=False)]
                else:
                    df_proprios = df_v
            except Exception:
                df_proprios = df_v

            sub1, sub2 = st.tabs(["📋 Alugados / Terceirizados", "🏢 Próprios"])
            with sub1:
                if not df_alugados.empty:
                    render_cards_veiculos(df_alugados)
                else:
                    # Se o filtro específico falhar, mostra todos para garantir visualização imediata
                    st.info("Nenhum veículo com filtro exato de alugado encontrado. A listar todos:")
                    render_cards_veiculos(df_v)
            with sub2:
                if not df_proprios.empty:
                    render_cards_veiculos(df_proprios)
                else:
                    render_cards_veiculos(df_v)
        else:
            st.info("Nenhum veículo registado na base de dados.")

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
            df_oc = pd.read_sql_query("SELECT o.id, v.placa, o.descricao, o.status FROM ocorrencias o JOIN veiculos v ON o.veiculo_id = v.id WHERE LOWER(o.status) IN ('pendente', 'aberto', 'em análise')", conn)
            conn.close()
            if not df_oc.empty:
                st.dataframe(df_oc, use_container_width=True, hide_index=True)
            else:
                st.success("Nenhuma ocorrência pendente!")
        except Exception:
            st.info("Sem ocorrências.")

    with st.expander("🛠️ Diagnóstico de Checklists (Ver Dados Crus)"):
        st.write("Últimos registos encontrados na tabela `checklists`:")
        if not dados["df_debug_checklists"].empty:
            st.dataframe(dados["df_debug_checklists"], use_container_width=True)
        else:
            st.warning("Nenhum registo encontrado na tabela `checklists` ou a tabela está vazia.")
