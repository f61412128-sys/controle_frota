import datetime
import sqlite3
import pandas as pd
import streamlit as st
from database.connection import get_connection


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
        "SELECT COUNT(*) FROM veiculos WHERE status != 'Inativo' AND (LOWER(tipo_propriedade) LIKE '%proprio%' OR LOWER(tipo_propriedade) LIKE '%próprio%')"
    ).fetchone()[0]

    qtd_alugados = cursor.execute(
        """
        SELECT COUNT(*) FROM veiculos 
        WHERE status != 'Inativo' 
          AND (LOWER(tipo_propriedade) LIKE '%alugado%' OR LOWER(tipo_propriedade) LIKE '%terceirizado%' OR LOWER(tipo_propriedade) LIKE '%locado%')
    """
    ).fetchone()[0]

    # Contadores de motoristas
    try:
        qtd_motoristas = cursor.execute(
            "SELECT COUNT(*) FROM motoristas WHERE status = 'Ativo'"
        ).fetchone()[0]
    except Exception:
        qtd_motoristas = 0

    # Manutenções e Custo Total dinâmico (Varre todas as colunas numéricas possíveis)
    qtd_manut_andamento = 0
    custo_total_manut = 0.0
    try:
        qtd_manut_andamento = cursor.execute(
            "SELECT COUNT(*) FROM manutencoes WHERE LOWER(status) LIKE '%andamento%'"
        ).fetchone()[0]
    except Exception:
        pass

    try:
        colunas_manut = [info[1] for info in cursor.execute("PRAGMA table_info(manutencoes)").fetchall()]
        df_manut_raw_sql = pd.read_sql_query("SELECT * FROM manutencoes", conn)
        
        # Encontrar qual coluna representa o valor/custo
        col_valor_encontrada = None
        for c in ["valor", "custo", "preco", "valor_total", "total", "gastos", "valor_servico"]:
            if c in df_manut_raw_sql.columns:
                col_valor_encontrada = c
                break
        
        if col_valor_encontrada and not df_manut_raw_sql.empty:
            # Limpa e converte para numérico com segurança
            valores_limpos = pd.to_numeric(
                df_manut_raw_sql[col_valor_encontrada].astype(str).str.replace('R$', '', regex=True).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
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
            elif "servico_realizado" in df_m_raw.columns:
                cols["servico_realizado"] = "Serviço"
            if "oficina" in df_m_raw.columns:
                cols["oficina"] = "Oficina"
            if col_valor_encontrada and col_valor_encontrada in df_m_raw.columns:
                cols[col_valor_encontrada] = "Valor (R$)"
            if "status" in df_m_raw.columns:
                cols["status"] = "Status"
            if "data_entrada" in df_m_raw.columns:
                cols["data_entrada"] = "Data Entrada"

            df_manutencoes = df_m_raw[[c for c in cols.keys() if c in df_m_raw.columns]].rename(columns=cols)
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
            .str.contains("alugado|terceirizado|locado", na=False)
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


def render_dashboard(contar_registros_fn=None):
    st.title("📊 Painel Geral")

    try:
        dados = carregar_dados_dashboard()
    except Exception as e:
        st.error(f"Erro ao carregar dados do painel: {e}")
        dados = {
            "veiculos": 0,
            "proprios": 0,
            "alugados": 0,
            "contratos_atencao": 0,
            "motoristas": 0,
            "manut_andamento": 0,
            "custo_total": 0.0,
            "pendencias": 0,
            "df_manutencoes": pd.DataFrame(),
            "df_veiculos_completo": pd.DataFrame(),
        }

    # --- CARDS DE MÉTRICAS PRINCIPAIS ---
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

    # --- ABAS INFORMATIVAS ---
    tab_contratos, tab_rodizio, tab_manut, tab_pendencias, tab_stats = st.tabs([
        "📄 Gestão de Contratos & Frota",
        "🚘 Rodízio Hoje",
        "🛠 Manutenções Recentes",
        "⚠ Ocorrências & Defeitos",
        "📊 Stats Banco",
    ])

    with tab_contratos:
        st.markdown("##### Detalhamento por Propriedade e Contratos")
        df_v = dados["df_veiculos_completo"]

        if not df_v.empty:
            df_proprios = df_v[
                df_v["tipo_propriedade"]
                .str.lower()
                .str.contains("próprio|proprio", na=False)
            ]
            df_alugados = df_v[
                df_v["tipo_propriedade"]
                .str.lower()
                .str.contains("alugado|terceirizado|locado", na=False)
            ]

            sub1, sub2 = st.tabs(
                ["📋 Veículos Alugados / Terceirizados", "🏢 Veículos Próprios"]
            )

            with sub1:
                if not df_alugados.empty:
                    cols_alugados = [
                        "placa",
                        "marca",
                        "modelo",
                        "locadora",
                        "inicio_contrato",
                        "fim_contrato",
                        "valor_mensal",
                    ]
                    st.dataframe(
                        df_alugados[[c for c in cols_alugados if c in df_alugados.columns]],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Nenhum veículo alugado/terceirizado encontrado na base.")

            with sub2:
                if not df_proprios.empty:
                    cols_proprios = [
                        "placa",
                        "marca",
                        "modelo",
                        "tipo_propriedade",
                    ]
                    st.dataframe(
                        df_proprios[[c for c in cols_proprios if c in df_proprios.columns]],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Nenhum veículo próprio cadastrado.")
        else:
            st.info("Nenhum veículo cadastrado na frota.")

    with tab_rodizio:
        st.markdown("##### Consulta rápida de restrição de circulação (SP)")
        dias = [
            "Segunda-feira",
            "Terça-feira",
            "Quarta-feira",
            "Quinta-feira",
            "Sexta-feira",
            "Sábado",
            "Domingo",
        ]
        hoje_idx = datetime.datetime.now().weekday()
        dia_hoje = dias[hoje_idx]

        regras = {
            0: "Placas finais 1 e 2",
            1: "Placas finais 3 e 4",
            2: "Placas finais 5 e 6",
            3: "Placas finais 7 e 8",
            4: "Placas finais 9 e 0",
        }

        restricao = regras.get(hoje_idx, "Sem restrição hoje")

        st.write(f"**Hoje:** {dia_hoje}")
        if hoje_idx < 5:
            st.warning(f"🚫 **Restrição hoje:** {restricao}")
            st.caption("Horários: 07h às 10h | 17h às 20h")
        else:
            st.success("✅ Sem restrição de rodízio aos finais de semana.")

    with tab_manut:
        st.markdown("##### Últimas Manutenções Registradas")
        if not dados["df_manutencoes"].empty:
            st.dataframe(
                dados["df_manutencoes"],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma manutenção registrada até o momento.")

    with tab_pendencias:
        st.markdown("##### Ocorrências em Aberto (Apontadas no Checklist)")
        try:
            conn = get_connection()
            df_oc = pd.read_sql_query(
                """
                SELECT 
                    o.id AS 'ID',
                    v.placa AS 'Veículo',
                    o.descricao AS 'Descrição',
                    o.status AS 'Status'
                FROM ocorrencias o
                JOIN veiculos v ON o.veiculo_id = v.id
                WHERE LOWER(o.status) IN ('pendente', 'aberto', 'em análise')
                ORDER BY o.id DESC
            """,
                conn,
            )
            conn.close()

            if not df_oc.empty:
                st.dataframe(df_oc, use_container_width=True, hide_index=True)
            else:
                st.success("Nenhuma ocorrência pendente no momento!")
        except Exception:
            st.info("Nenhuma ocorrência registrada.")

    with tab_stats:
        st.markdown("##### 🗄️ Total de Registros no Banco de Dados")
        if contar_registros_fn:
            stats = contar_registros_fn()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🚗 Veículos", stats.get("veiculos", 0))
            c2.metric("👨‍✈️ Motoristas", stats.get("motoristas", 0))
            c3.metric("👥 Usuários", stats.get("usuarios", 0))
            c4.metric("📋 Checklists", stats.get("checklists", 0))

            st.write("")
            c5, c6, c7, c8 = st.columns(4)
            c5.metric("🛠 Manutenções", stats.get("manutencoes", 0))
            c6.metric("⚠ Ocorrências", stats.get("ocorrencias", 0))
            c7.metric("📝 Itens Checklist", stats.get("itens_checklist", 0))
        else:
            st.info("Informações estatísticas do banco indisponíveis.")
