import datetime
import pandas as pd
import streamlit as st
from database.connection import get_connection
from views.services.cadastros_service import listar_veiculos


def salvar_abastecimento(veiculo_id, km, litros, valor, foto_bytes, usuario):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Cria a tabela de abastecimentos automaticamente caso não exista
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS abastecimentos (
                id SERIAL PRIMARY KEY,
                veiculo_id INT,
                km NUMERIC,
                litros NUMERIC,
                valor NUMERIC,
                foto BYTEA,
                usuario TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        cursor.execute("""
            INSERT INTO abastecimentos (veiculo_id, km, litros, valor, foto, usuario, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (veiculo_id, km, litros, valor, foto_bytes, usuario))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def render():
    st.title("⛽ Gestão de Abastecimentos")

    tab_novo, tab_hist = st.tabs(["📝 Registar Abastecimento", "📊 Histórico de Consumo"])

    with tab_novo:
        st.caption("Registe o abastecimento e envie o comprovante.")
        veiculos = listar_veiculos()
        
        if not veiculos:
            st.warning("É necessário ter veículos cadastrados para registar abastecimentos.")
            return

        mapa_v = {f"{v['placa']} - {v['modelo']}": v["id"] for v in veiculos}
        veiculo_sel = st.selectbox("Selecione o Veículo*", list(mapa_v.keys()))
        veiculo_id = mapa_v[veiculo_sel]

        usuario = st.session_state.get("usuario_nome", st.session_state.get("usuario", "Administrador"))

        col1, col2 = st.columns(2)
        with col1:
            km = st.number_input("Quilometragem Atual (KM)*", min_value=0.0, step=1.0)
        with col2:
            litros = st.number_input("Litros Abastecidos*", min_value=0.0, step=0.1)

        valor = st.number_input("Valor Total Gasto (R$)*", min_value=0.0, step=0.01)

        st.divider()
        st.subheader("📸 Comprovante / Nota Fiscal")
        
        tipo_envio = st.radio("Método de captura da foto:", ["Tirar Foto com a Câmara", "Carregar Imagem"], horizontal=True)
        foto_bytes = None

        if tipo_envio == "Tirar Foto com a Câmara":
            foto = st.camera_input("Aponte para o comprovante de abastecimento")
            if foto:
                foto_bytes = foto.getvalue()
        else:
            foto_arq = st.file_uploader("Carregar imagem do comprovante", type=["png", "jpg", "jpeg"])
            if foto_arq:
                foto_bytes = foto_arq.getvalue()

        if st.button("✅ Salvar Abastecimento", use_container_width=True):
            try:
                salvar_abastecimento(veiculo_id, km, litros, valor, foto_bytes, usuario)
                st.success("Abastecimento registado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar abastecimento: {e}")

    with tab_hist:
        st.subheader("Histórico de Consumo e Abastecimentos")
        conn = get_connection()
        try:
            query = """
                SELECT 
                    a.id,
                    v.placa,
                    v.modelo,
                    a.km,
                    a.litros,
                    a.valor,
                    a.usuario,
                    a.created_at
                FROM abastecimentos a
                LEFT JOIN veiculos v ON a.veiculo_id = v.id
                ORDER BY a.id DESC
            """
            df = pd.read_sql(query, conn)
            if df.empty:
                st.info("Nenhum abastecimento registado até o momento.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception:
            st.info("A tabela de abastecimentos ainda não possui registos.")
        finally:
            conn.close()
