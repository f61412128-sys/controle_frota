import pandas as pd
import streamlit as st
from database.connection import get_connection
from views.services.cadastros_service import listar_veiculos


def garantir_tabela_manutencoes():
    """Garante que a tabela manutencoes existe com todas as colunas necessárias."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS manutencoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                veiculo_id INTEGER,
                tipo TEXT,
                status TEXT,
                problema TEXT,
                oficina TEXT,
                km REAL,
                valor REAL,
                data_entrada TEXT,
                proximo_km REAL,
                FOREIGN KEY (veiculo_id) REFERENCES veiculos (id)
            )
        """
        )
        conn.commit()
    except Exception as e:
        print(f"Erro ao criar tabela de manutenções: {e}")
    finally:
        conn.close()


def salvar_manutencao(
    veiculo_id,
    tipo,
    status,
    problema,
    oficina,
    km,
    valor,
    data_entrada,
    proximo_km,
):
    """Insere o registo de manutenção utilizando a conexão oficial do sistema."""
    garantir_tabela_manutencoes()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO manutencoes (
                veiculo_id, tipo, status, problema, oficina, km, valor, data_entrada, proximo_km
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                veiculo_id,
                tipo,
                status,
                problema,
                oficina,
                km,
                valor,
                str(data_entrada),
                proximo_km,
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def carregar_manutencoes():
    """Carrega o histórico de manutenções utilizando a conexão oficial do sistema."""
    garantir_tabela_manutencoes()
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            """
            SELECT m.id, v.placa, v.modelo, m.tipo, m.status, m.problema AS descricao, 
                   m.oficina, m.km, m.valor, m.data_entrada, m.proximo_km
            FROM manutencoes m
            JOIN veiculos v ON m.veiculo_id = v.id
            ORDER BY m.id DESC
        """,
            conn,
        )
        # Garante que a coluna valor seja sempre tratada como numérica (float)
        if not df.empty and "valor" in df.columns:
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def render():
    st.title("🛠️ Controle de Manutenções")

    tab1, tab2, tab3 = st.tabs([
        "📋 Histórico",
        "➕ Nova Manutenção",
        "📊 Custos & Indicadores",
    ])

    # --- TAB 1: HISTÓRICO ---
    with tab1:
        st.subheader("Manutenções Registradas")
        df_manut = carregar_manutencoes()
        if not df_manut.empty:
            st.dataframe(
                df_manut[
                    [
                        "placa",
                        "modelo",
                        "tipo",
                        "status",
                        "descricao",
                        "oficina",
                        "valor",
                        "data_entrada",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma manutenção registrada na frota.")

    # --- TAB 2: NOVA MANUTENÇÃO ---
    with tab2:
        st.subheader("Registrar Serviço / Revisão")

        veiculos = listar_veiculos()
        mapa_veiculos = {
            f"{v['placa']} - {v['modelo']}": v["id"] for v in veiculos
        }

        if not mapa_veiculos:
            st.warning(
                "Cadastre veículos primeiro para poder registar manutenções."
            )
            return

        with st.form("form_manutencao", clear_on_submit=True):
            veiculo_sel = st.selectbox(
                "Veículo*", list(mapa_veiculos.keys())
            )

            col1, col2 = st.columns(2)
            tipo = col1.selectbox("Tipo de Manutenção*", ["Preventiva", "Corretiva"])
            status = col2.selectbox(
                "Status*", ["Concluída", "Em andamento", "Agendada"]
            )

            descricao = st.text_area(
                "Descrição dos Serviços / Peças Trocadas*"
            )

            col3, col4, col5 = st.columns(3)
            oficina = col3.text_input("Oficina / Prestador")
            km_registro = col4.number_input("KM Atual do Veículo", min_value=0)
            custo = col5.number_input(
                "Custo Total (R$)", min_value=0.0, format="%.2f", step=50.0
            )

            col6, col7 = st.columns(2)
            data_manut = col6.date_input("Data do Serviço")
            proximo_km = col7.number_input(
                "Próxima Revisão (KM)", min_value=0, value=15000
            )

            btn_salvar = st.form_submit_button("Salvar Manutenção")

            if btn_salvar:
                if veiculo_sel and descricao:
                    try:
                        veiculo_id = mapa_veiculos[veiculo_sel]
                        salvar_manutencao(
                            veiculo_id=veiculo_id,
                            tipo=tipo,
                            status=status,
                            problema=descricao,
                            oficina=oficina,
                            km=km_registro,
                            valor=custo,
                            data_entrada=data_manut,
                            proximo_km=proximo_km,
                        )
                        st.success("Manutenção registrada e salva com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar manutenção: {e}")
                else:
                    st.warning("Preencha todos os campos obrigatórios.")

    # --- TAB 3: CUSTOS & INDICADORES ---
    with tab3:
        st.subheader("Resumo Financeiro da Frota")
        df_manut = carregar_manutencoes()

        if not df_manut.empty:
            gasto_total = df_manut["valor"].sum()
            st.metric(
                label="Gasto Total em Manutenção",
                value=f"R$ {gasto_total:,.2f}",
            )

            st.divider()
            st.markdown("##### Custos por Veículo")
            df_custos = (
                df_manut.groupby(["placa", "modelo"])["valor"]
                .sum()
                .reset_index()
            )
            df_custos.columns = ["Placa", "Modelo", "Custo Total (R$)"]
            st.dataframe(df_custos, use_container_width=True, hide_index=True)
        else:
            st.metric(label="Gasto Total em Manutenção", value="R$ 0,00")
            st.info("Registe manutenções para visualizar os indicadores financeiros.")
