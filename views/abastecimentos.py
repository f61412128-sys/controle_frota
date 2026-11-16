import datetime
import io
import pandas as pd
import streamlit as st
from PIL import Image
from database.connection import get_connection
from views.services.cadastros_service import listar_veiculos


def garantir_estrutura_abastecimentos(cursor):
    """Garante a existência da tabela e da coluna adicional para a foto do odômetro."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS abastecimentos (
            id SERIAL PRIMARY KEY,
            veiculo_id INT,
            km NUMERIC,
            litros NUMERIC,
            valor NUMERIC,
            foto BYTEA,
            foto_odometro BYTEA,
            usuario TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        "ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS foto_odometro BYTEA;"
    )


def salvar_abastecimento(
    veiculo_id, km, litros, valor, foto_cupom_bytes, foto_odometro_bytes, usuario
):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        garantir_estrutura_abastecimentos(cursor)
        conn.commit()

        agora_local = datetime.datetime.now()

        cursor.execute(
            """
            INSERT INTO abastecimentos (
                veiculo_id, km, litros, valor, foto, foto_odometro, usuario, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                veiculo_id,
                km,
                litros,
                valor,
                foto_cupom_bytes,
                foto_odometro_bytes,
                usuario,
                agora_local,
            ),
        )

        # --- ATUALIZAÇÃO AUTOMÁTICA DO KM DO VEÍCULO ---
        cursor.execute(
            "UPDATE veiculos SET km_atual = %s WHERE id = %s", (km, veiculo_id)
        )

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def render_captura_imagem(titulo, chave_prefixo, legenda_preview):
    """Componente reutilizável para capturar ou carregar imagem com pré-visualização."""
    st.subheader(titulo)

    state_key = f"{chave_prefixo}_bytes"
    if state_key not in st.session_state:
        st.session_state[state_key] = None

    tipo_envio = st.radio(
        "Método de captura da foto:",
        ["Tirar Foto com a Câmara", "Carregar Imagem"],
        horizontal=True,
        key=f"tipo_envio_{chave_prefixo}",
    )

    if tipo_envio == "Tirar Foto com a Câmara":
        foto_cam = st.camera_input(
            f"Capturar imagem ({titulo})", key=f"cam_{chave_prefixo}"
        )
        if foto_cam is not None:
            st.session_state[state_key] = foto_cam.getvalue()
    else:
        foto_arq = st.file_uploader(
            f"Carregar arquivo ({titulo})",
            type=["png", "jpg", "jpeg", "heic"],
            key=f"file_{chave_prefixo}",
        )
        if foto_arq is not None:
            st.session_state[state_key] = foto_arq.getvalue()

    if st.session_state[state_key] is not None:
        try:
            img_preview = Image.open(io.BytesIO(st.session_state[state_key]))
            st.image(img_preview, caption=legenda_preview, width=200)
            if st.button(
                "🗑 Limpar / Tirar Outra Foto",
                key=f"btn_limpar_{chave_prefixo}",
            ):
                st.session_state[state_key] = None
                st.rerun()
        except Exception:
            pass


def render():
    st.title("⛽ Gestão de Abastecimentos")

    tab_novo, tab_hist = st.tabs(
        ["📝 Registar Abastecimento", "📊 Histórico de Consumo"]
    )

    with tab_novo:
        st.caption(
            "Registe o abastecimento e envie as fotos do odômetro e do cupom fiscal."
        )
        veiculos = listar_veiculos()

        if not veiculos:
            st.warning(
                "É necessário ter veículos cadastrados para registar abastecimentos."
            )
            return

        mapa_v = {f"{v['placa']} - {v['modelo']}": v["id"] for v in veiculos}
        veiculo_sel = st.selectbox(
            "Selecione o Veículo*", list(mapa_v.keys())
        )
        veiculo_id = mapa_v[veiculo_sel]

        usuario = st.session_state.get(
            "usuario_nome",
            st.session_state.get("usuario", "Motorista / Administrador"),
        )

        col1, col2 = st.columns(2)
        with col1:
            km = st.number_input(
                "Quilometragem Atual (KM)*", min_value=0.0, step=1.0
            )
        with col2:
            litros = st.number_input(
                "Litros Abastecidos*", min_value=0.0, step=0.1
            )

        valor = st.number_input(
            "Valor Total Gasto (R$)*", min_value=0.0, step=0.01
        )

        st.divider()

        # 1. Captura da Foto do Odômetro
        render_captura_imagem(
            titulo="⏲️ 1. Foto do Odômetro (Painel KM)",
            chave_prefixo="abast_odometro",
            legenda_preview="⏲️ Pré-visualização do Odômetro",
        )

        st.divider()

        # 2. Captura da Foto do Cupom Fiscal
        render_captura_imagem(
            titulo="🧾 2. Foto do Cupom Fiscal / Comprovante",
            chave_prefixo="abast_cupom",
            legenda_preview="🧾 Pré-visualização do Cupom Fiscal",
        )

        st.divider()

        if st.button("✅ Salvar Abastecimento", use_container_width=True):
            try:
                foto_odometro_bytes = st.session_state.get(
                    "abast_odometro_bytes", None
                )
                foto_cupom_bytes = st.session_state.get(
                    "abast_cupom_bytes", None
                )

                salvar_abastecimento(
                    veiculo_id,
                    km,
                    litros,
                    valor,
                    foto_cupom_bytes,
                    foto_odometro_bytes,
                    usuario,
                )

                st.session_state["abast_odometro_bytes"] = None
                st.session_state["abast_cupom_bytes"] = None

                st.success("Abastecimento registado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar abastecimento: {e}")

    with tab_hist:
        st.subheader("Histórico de Consumo e Abastecimentos")
        conn = get_connection()
        try:
            cursor = conn.cursor()
            garantir_estrutura_abastecimentos(cursor)
            conn.commit()
            cursor.close()

            query = """
                SELECT 
                    a.id,
                    v.placa,
                    v.modelo,
                    a.km,
                    a.litros,
                    a.valor,
                    a.usuario,
                    a.created_at,
                    a.foto,
                    a.foto_odometro
                FROM abastecimentos a
                LEFT JOIN veiculos v ON a.veiculo_id = v.id
                ORDER BY a.id DESC
            """
            df = pd.read_sql(query, conn)
            if df.empty:
                st.info("Nenhum abastecimento registado até o momento.")
            else:
                for _, row in df.iterrows():
                    raw_data = row["created_at"]
                    if pd.notna(raw_data):
                        try:
                            dt_parsed = pd.to_datetime(raw_data)
                            dt_ajustado = dt_parsed - pd.Timedelta(hours=3)
                            data_formatada = dt_ajustado.strftime(
                                "%d/%m/%Y %H:%M"
                            )
                        except Exception:
                            data_formatada = str(raw_data)
                    else:
                        data_formatada = "N/A"

                    st.markdown(
                        f"**ID:** {row['id']} | **Veículo:** {row['placa']} - {row['modelo']} | **KM:** {row['km']} | **Litros:** {row['litros']} | **Valor:** R$ {row['valor']} | **Data:** {data_formatada}"
                    )

                    foto_odo_db = row.get("foto_odometro")
                    foto_cupom_db = row.get("foto")

                    tem_odo = foto_odo_db is not None and len(bytes(foto_odo_db)) > 0
                    tem_cupom = foto_cupom_db is not None and len(bytes(foto_cupom_db)) > 0

                    if tem_odo or tem_cupom:
                        col_img1, col_img2, _ = st.columns([1, 1, 3])
                        with col_img1:
                            if tem_odo:
                                try:
                                    img_odo = Image.open(io.BytesIO(bytes(foto_odo_db)))
                                    st.image(
                                        img_odo,
                                        caption=f"⏲️ Odômetro (#{row['id']})",
                                        width=140,
                                    )
                                except Exception:
                                    pass
                        with col_img2:
                            if tem_cupom:
                                try:
                                    img_cupom = Image.open(io.BytesIO(bytes(foto_cupom_db)))
                                    st.image(
                                        img_cupom,
                                        caption=f"🧾 Cupom (#{row['id']})",
                                        width=140,
                                    )
                                except Exception:
                                    pass

                    st.divider()
        except Exception:
            st.info("A tabela de abastecimentos ainda não possui registos.")
        finally:
            conn.close()
