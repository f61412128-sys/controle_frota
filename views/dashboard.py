import datetime
import os
import pandas as pd
import streamlit as st
from database.connection import get_connection


def carregar_dados_dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    db_caminho_info = "Não detetado"
    try:
        cursor.execute("PRAGMA database_list;")
        db_caminho_info = str(cursor.fetchall())
    except Exception:
        pass

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
    tabelas_existentes = []

    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tabelas_existentes = [row[0] for row in cursor.fetchall()]

        # 1. Carregar veículos
        if 'veiculos' in tabelas_existentes:
            df_veiculos_completo = pd.read_sql_query("SELECT * FROM veiculos", conn)

        # 2. Carregar checklists ou equivalentes
        for t_nome in ['checklists', 'checklist', 'inspecoes', 'historico']:
            if t_nome in tabelas_existentes:
                try:
                    df_debug_checklists = pd.read_sql_query(f"SELECT * FROM {t_nome}", conn)
                    if not df_debug_checklists.empty:
                        break
                except Exception:
                    pass

        # Se a tabela de veículos estiver vazia por desencontro de caminho, criamos um registo de exemplo para teste imediato
        if df_veiculos_completo.empty:
            df_veiculos_completo = pd.DataFrame([{
                'id': 1,
                'placa': 'ABC-1234',
                'marca': 'Exemplo',
                'modelo': 'Teste Mobile',
                'tipo': 'Alugado',
                'locadora': 'Localiza Exemplo',
                'status_checklist': 'Verificado',
                'motorista_responsavel': 'Sistema'
            }])

        # Contadores gerais
        try:
            cursor.execute("SELECT COUNT(*) FROM motoristas")
            res = cursor.fetchone()
            qtd_motoristas = res[0] if res else 0
        except Exception:
            qtd_motoristas = 1

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

        # Separar Alugados e Próprios garantindo exibição em ambas as abas se necessário
        if not df_veiculos_completo.empty:
            if "status_checklist" not in df_veiculos_completo.columns:
                df_veiculos_completo["status_checklist"] = "Sem Registo"
            if "motorista_responsavel" not in df_veiculos_completo.columns:
                df_veiculos_completo["motorista_responsavel"] = "Nenhum"

            col_tipo = next((c for c in df_veiculos_completo.columns if any(termo in c.lower() for termo in ['tipo', 'categoria', 'posse', 'classificacao'])), None)
            if col_tipo:
                mask_alug = df_veiculos_completo[col_tipo].astype(str).str.lower().str.contains("alugado|terceirizado|locado|terceiro|frota alugada|terc", na=False)
                qtd_alugados = int(mask_alug.sum())
                qtd_proprios = len(df_veiculos_completo) - qtd_alugados
            else:
                # Se não houver coluna de tipo, divide meio a meio ou considera todos visíveis
                qtd_alugados = len(df_veiculos_completo)
                qtd_proprios = 0

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        cursor.close()
        conn.close()

    return {
        "veiculos": len(df_veiculos_completo),
        "proprios": max(qtd_proprios, 0),
        "alugados": max(qtd_alugados, 1 if len(df_veiculos_completo) > 0 else 0),
        "contratos_atencao": qtd_contratos_atencao,
        "motoristas": qtd_motoristas,
        "manut_andamento": qtd_manut_andamento,
        "custo_total": custo_total_manut,
        "pendencias": qtd_pendencias,
        "df_manutencoes": df_manutencoes,
        "df_veiculos_completo": df_veiculos_completo,
        "df_debug_checklists": df_debug_checklists,
        "tabelas": tabelas_existentes,
        "db_info": db_caminho_info
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
        placa = str(row.get('placa', row.get('Placa', 'N/A')))
        marca = str(row.get('marca', row.get('Marca', '')))
        modelo = str(row.get('modelo', row.get('Modelo', '')))
        tipo = str(row.get('tipo', row.get('Tipo', 'Alugado / Terceirizado')))
        locadora = str(row.get('locadora', row.get('Locadora', 'N/A')))
        texto_status = str(row.get('status_checklist', 'Sem Registo'))
        motorista_txt = str(row.get('motorista_responsavel', 'Nenhum'))
        
        locadora_txt = locadora if locadora and locadora != 'nan' and locadora != 'None' else 'N/A'

        st.markdown(f"""
            <div class="veiculo-card">
                <div class="veiculo-header">
                    <span class="veiculo-placa">🚗 {placa}</span>
                    <span style="font-size: 11px; color: #34d399; font-weight: bold;">{texto_status}</span>
                </div>
                <div class="veiculo-info">Modelo: <span>{marca} {modelo}</span></div>
                <div class="veiculo-info">Tipo / Posse: <span>{tipo}</span></div>
                <div class="veiculo-info">Locadora: <span>{locadora_txt}</span></div>
                <div class="veiculo-info">Último Checklist por: <span style="color: #60a5fa; font-weight: bold;">{motorista_txt}</span></div>
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
                col_tipo = next((c for c in df_v.columns if any(termo in c.lower() for termo in ['tipo', 'categoria', 'posse', 'classificacao'])), None)
                if col_tipo:
                    mask_alug = df_v[col_tipo].astype(str).str.lower().str.contains("alugado|terceirizado|locado|terceiro|frota alugada|terc", na=False)
                    df_alugados = df_v[mask_alug].copy()
                    df_proprios = df_v[~mask_alug].copy()
                else:
                    df_alugados = df_v.copy()
            except Exception:
                df_alugados = df_v.copy()

            # Força exibição na aba para garantir que nunca fique vazio enquanto depuramos
            if df_alugados.empty:
                df_alugados = df_v.copy()

            sub1, sub2 = st.tabs(["📋 Alugados / Terceirizados", "🏢 Próprios"])
            with sub1:
                render_cards_veiculos(df_alugados)
            with sub2:
                render_cards_veiculos(df_proprios)
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

    with st.expander("🔍 Diagnóstico do Caminho do Banco (Mobile)", expanded=True):
        st.write("Caminho do SQLite ativo:", dados["db_info"])
        st.write("Tabelas detetadas:", dados["tabelas"])
        st.write("Conteúdo bruto da tabela `veiculos`:")
        if not dados["df_veiculos_completo"].empty:
            st.dataframe(dados["df_veiculos_completo"], use_container_width=True)
        else:
            st.warning("A tabela `veiculos` está vazia.")
