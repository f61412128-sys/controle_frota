import datetime
import io
import json
import urllib.request
from PIL import Image
import pandas as pd
import streamlit as st
import psycopg2.extras
from database.connection import get_connection
from views.services.cadastros_service import listar_motoristas, listar_veiculos


def obter_localizacao_ip():
    """Obtém coordenadas aproximadas via IP/Rede como alternativa segura e fiável."""
    try:
        url = "https://ipapi.co/json/"
        req = urllib.request.Request(url, headers={"User-Agent": "ControleFrotaApp/1.0"})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if "latitude" in data and "longitude" in data:
                return f"{data['latitude']}, {data['longitude']}"
    except Exception:
        pass
    return None


def obter_endereco_reverso(lat_lon_str):
    """Converte coordenadas num endereço limpo e legível (Rua, Bairro, Cidade) via Nominatim."""
    try:
        if not lat_lon_str or "Erro" in lat_lon_str or "Não" in lat_lon_str:
            lat_lon_str = obter_localizacao_ip() or "-23.5505, -46.6333"

        if "," in lat_lon_str:
            partes = lat_lon_str.split(",")
            if len(partes) == 2:
                lat = partes[0].strip()
                lon = partes[1].strip()

                # User-Agent obrigatório e válido para evitar bloqueios da API Nominatim
                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
                req = urllib.request.Request(
                    url, headers={"User-Agent": "ControleFrotaApp-Prod/2.0 (suporte@controlefrota.local)"}
                )

                with urllib.request.urlopen(req, timeout=6) as response:
                    data = json.loads(response.read().decode())
                    if "address" in data:
                        addr = data["address"]
                        rua = addr.get("road") or addr.get("pedestrian") or addr.get("street") or addr.get("suburb") or ""
                        bairro = addr.get("suburb") or addr.get("neighbourhood") or addr.get("city_district") or ""
                        cidade = addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("state") or ""
                        
                        partes_endereco = [p for p in [rua, bairro, cidade] if p]
                        if partes_endereco:
                            return ", ".join(partes_endereco)
                            
                    if "display_name" in data:
                        return data["display_name"]
    except Exception:
        pass

    return lat_lon_str


def salvar_checklist(
    veiculo_id,
    motorista_id,
    tipo_operacao,
    km,
    itens_respostas,
    observacoes,
    foto_bytes,
    localizacao,
    usuario_responsavel,
):
    if not localizacao or "não" in localizacao.lower() or "," not in localizacao:
        localizacao = obter_localizacao_ip() or "-23.5505, -46.6333"

    localizacao_amigavel = obter_endereco_reverso(localizacao)
    
    fuso_brasilia = datetime.timezone(datetime.timedelta(hours=-3))
    data_hora_atual = datetime.datetime.now(fuso_brasilia).strftime("%Y-%m-%d %H:%M:%S")

    foto_param = psycopg2.Binary(foto_bytes) if foto_bytes else None

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'checklists'"
        )
        colunas_chk = [col[0] for col in cursor.fetchall()]

        for col_nome, col_tipo in [
            ("localizacao", "TEXT"),
            ("foto", "BYTEA"),
            ("tipo_operacao", "TEXT"),
            ("usuario_responsavel", "TEXT"),
            ("created_at", "TIMESTAMP"),
        ]:
            if col_nome not in colunas_chk:
                try:
                    cursor.execute(f"ALTER TABLE checklists ADD COLUMN {col_nome} {col_tipo}")
                    conn.commit()
                except Exception:
                    conn.rollback()

        tem_pendencia = any(res == "NÃO OK" for res in itens_respostas.values())
        resultado_geral = "Com pendências" if tem_pendencia else "Aprovado"

        cursor.execute(
            """
            INSERT INTO checklists (veiculo_id, motorista_id, tipo_operacao, km, resultado, observacoes, localizacao, foto, usuario_responsavel, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                veiculo_id,
                motorista_id if motorista_id else 1,
                tipo_operacao,
                km,
                resultado_geral,
                observacoes,
                localizacao_amigavel,
                foto_param,
                usuario_responsavel,
                data_hora_atual,
            ),
        )
        checklist_id = cursor.fetchone()[0]

        for (categoria, item), resp in itens_respostas.items():
            cursor.execute(
                """
                INSERT INTO itens_checklist (checklist_id, categoria, item, resultado)
                VALUES (%s, %s, %s, %s)
                """,
                (checklist_id, categoria, item, resp),
            )

            if resp == "NÃO OK":
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'ocorrencias'"
                )
                colunas_oco = [col[0] for col in cursor.fetchall()]

                for c_nome, c_tipo in [("foto", "BYTEA"), ("usuario_responsavel", "TEXT"), ("created_at", "TIMESTAMP")]:
                    if c_nome not in colunas_oco:
                        try:
                            cursor.execute(f"ALTER TABLE ocorrencias ADD COLUMN {c_nome} {c_tipo}")
                            conn.commit()
                        except Exception:
                            conn.rollback()

                val_oco = {
                    "veiculo_id": veiculo_id,
                    "motorista_id": motorista_id if motorista_id else 1,
                    "checklist_id": checklist_id,
                    "item": item,
                    "descricao": f"Avaria apontada no checklist (Local: {localizacao_amigavel}): {item}",
                    "status": "Aberto",
                    "usuario_responsavel": usuario_responsavel,
                    "foto": foto_param,
                    "created_at": data_hora_atual
                }
                if "gravidade" in colunas_oco:
                    val_oco["gravidade"] = "Média"

                cols = ", ".join(val_oco.keys())
                placeholders = ", ".join(["%s"] * len(val_oco))
                cursor.execute(
                    f"INSERT INTO ocorrencias ({cols}) VALUES ({placeholders})",
                    list(val_oco.values()),
                )

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


def buscar_historico_checklists():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'checklists'"
        )
        colunas_chk = [col[0] for col in cursor.fetchall()]

        if "created_at" in colunas_chk:
            col_data_sql = "c.created_at"
        elif "data" in colunas_chk:
            col_data_sql = "c.data"
        elif "data_criacao" in colunas_chk:
            col_data_sql = "c.data_criacao"
        else:
            col_data_sql = "NULL"

        col_loc_sql = "c.localizacao" if "localizacao" in colunas_chk else "'' AS localizacao"
        col_op_sql = "c.tipo_operacao" if "tipo_operacao" in colunas_chk else "'Saída (Retirada do Veículo)' AS tipo_operacao"
        col_resp_sql = "c.usuario_responsavel" if "usuario_responsavel" in colunas_chk else "NULL AS usuario_responsavel"
        col_foto_sql = "c.foto" if "foto" in colunas_chk else "NULL AS foto"

        query = f"""
            SELECT 
                c.id,
                {col_data_sql} AS created_at,
                c.km,
                c.resultado,
                c.observacoes,
                {col_loc_sql},
                {col_op_sql},
                {col_resp_sql},
                {col_foto_sql},
                v.placa,
                v.modelo,
                COALESCE(c.usuario_responsavel, m.nome, u.nome, 'Administrador') AS motorista_nome
            FROM checklists c
            LEFT JOIN veiculos v ON c.veiculo_id = v.id
            LEFT JOIN motoristas m ON c.motorista_id = m.id
            LEFT JOIN usuarios u ON c.motorista_id = u.id
            ORDER BY c.id DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        return [dict(zip(col_names, r)) for r in rows]
    finally:
        cursor.close()
        conn.close()


def buscar_itens_checklist(checklist_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT categoria, item, resultado FROM itens_checklist WHERE checklist_id = %s",
            (checklist_id,),
        )
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        return [dict(zip(col_names, r)) for r in rows]
    finally:
        cursor.close()
        conn.close()


def render():
    st.title("📲 Checklist Diário")

    tab_novo, tab_historico = st.tabs(
        ["📝 Preencher Checklist", "📊 Histórico & Consultas"]
    )

    # -------------------------------------------------------------------------
    # ABA 1: FORMULÁRIO DE NOVO CHECKLIST
    # -------------------------------------------------------------------------
    with tab_novo:
        st.caption("Preencha a inspeção do veículo com atenção.")

        veiculos = listar_veiculos()

        if not veiculos:
            st.warning(
                "É necessário ter veículos cadastrados no sistema para realizar o checklist."
            )
            return

        mapa_v = {
            f"{v['placa']} - {v['modelo']}": (v["id"], v["km_atual"])
            for v in veiculos
        }

        usuario_nome = st.session_state.get(
            "usuario_nome", st.session_state.get("usuario", "Administrador")
        )
        motorista_id = st.session_state.get("motorista_id")

        with st.form("form_checklist_oficial"):
            st.subheader("1. Identificação")
            veiculo_sel = st.selectbox("Selecione o Veículo*", list(mapa_v.keys()))
            veiculo_id, km_anterior = mapa_v[veiculo_sel]

            tipo_operacao = st.selectbox(
                "Tipo de Operação*",
                [
                    "Saída (Retirada do Veículo)",
                    "Entrada (Devolução ao Pátio)",
                ],
            )

            st.text_input("Responsável pelo Registo", value=usuario_nome, disabled=True)

            km = st.number_input(
                "Quilometragem Atual (KM)*",
                min_value=0,
                value=int(km_anterior),
            )

            st.divider()
            st.subheader("2. Inspeção de Itens")

            itens_checklist = [
                ("Pneus", "Calibragem e Estado Geral"),
                ("Fluidos", "Nível de Óleo do Motor"),
                ("Fluidos", "Nível de Água / Radiador"),
                ("Elétrica", "Faróis e Setas"),
                ("Elétrica", "Luzes de Freio e Ré"),
                ("Segurança", "Cinto de Segurança e Espelhos"),
                ("Estrutura", "Limpeza e Funilaria"),
            ]

            respostas = {}
            for cat, item in itens_checklist:
                respostas[(cat, item)] = st.radio(
                    f"**{item}**",
                    ["OK", "NÃO OK", "N/A"],
                    horizontal=True,
                    key=f"item_form_{cat}_{item}",
                )

            st.divider()
            st.subheader("3. Evidências e Observações")

            st.write("📸 **Fotografia da Avaria (Câmara ou Galeria)**")
            
            foto_camera = st.camera_input("Tirar foto com a câmara", key="cam_avaria_form")
            foto_upload = st.file_uploader(
                "Ou selecione um ficheiro da galeria", 
                type=["jpg", "jpeg", "png", "heic"],
                key="up_avaria_form"
            )

            obs = st.text_area("Observações / Detalhes de problemas", key="text_obs_form")

            st.markdown("<br>", unsafe_allow_html=True)

            submitted = st.form_submit_button("✅ Finalizar e Enviar Checklist", use_container_width=True)

            if submitted:
                foto_bytes = None
                if foto_camera is not None:
                    foto_bytes = foto_camera.getvalue()
                elif foto_upload is not None:
                    foto_bytes = foto_upload.getvalue()

                localizacao_capturada = obter_localizacao_ip() or "-23.5505, -46.6333"

                with st.spinner("A guardar o checklist e a converter endereço..."):
                    try:
                        salvar_checklist(
                            veiculo_id,
                            motorista_id,
                            tipo_operacao,
                            km,
                            respostas,
                            obs,
                            foto_bytes,
                            localizacao_capturada,
                            usuario_nome,
                        )
                        st.success("Checklist registrado e salvo com sucesso no sistema!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar checklist: {e}")

    # -------------------------------------------------------------------------
    # ABA 2: HISTÓRICO DE REGISTROS
    # -------------------------------------------------------------------------
    with tab_historico:
        st.caption(
            "Consulte os históricos de vistorias, avarias e localização exata reportada."
        )

        registros = buscar_historico_checklists()

        if not registros:
            st.info("Nenhum registo de checklist encontrado.")
            return

        total_rec = len(registros)
        total_pendencias = sum(
            1 for r in registros if r["resultado"] == "Com pendências"
        )

        m1, m2 = st.columns(2)
        m1.metric("Total de Inspeções", total_rec)
        m2.metric("Com Pendências", total_pendencias, delta_color="inverse")

        st.divider()

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            lista_veiculos_filtro = ["Todos"] + sorted(
                list(
                    set(
                        f"{r['placa']} - {r['modelo']}"
                        for r in registros
                        if r['placa']
                    )
                )
            )
            filtro_veiculo = st.selectbox(
                "Filtrar por Veículo", lista_veiculos_filtro
            )
        with col_f2:
            apenas_pendencias = st.checkbox("⚠ Apenas com Pendências")

        registros_filtrados = registros
        if filtro_veiculo != "Todos":
            registros_filtrados = [
                r
                for r in registros_filtrados
                if f"{r['placa']} - {r['modelo']}" == filtro_veiculo
            ]
        if apenas_pendencias:
            registros_filtrados = [
                r
                for r in registros_filtrados
                if r["resultado"] == "Com pendências"
            ]

        st.write(f"Exibindo **{len(registros_filtrados)}** registos:")

        for reg in registros_filtrados:
            status_icone = (
                "🔴" if reg["resultado"] == "Com pendências" else "🟢"
            )

            raw_data = reg.get("created_at")
            if isinstance(raw_data, datetime.datetime):
                data_formatada = raw_data.strftime("%d/%m/%Y %H:%M")
            elif raw_data and str(raw_data).strip() not in ["", "None", "NaT"]:
                data_str = str(raw_data).strip()
                data_formatada = (
                    data_str[:16].replace("T", " ")
                    if len(data_str) >= 16
                    else data_str
                )
            else:
                fuso_brasilia = datetime.timezone(datetime.timedelta(hours=-3))
                data_formatada = datetime.datetime.now(fuso_brasilia).strftime(
                    "%d/%m/%Y %H:%M"
                )

            localizacao_txt = reg.get("localizacao", "Não informada")
            op_txt = f" | 🔄 {reg.get('tipo_operacao', 'N/A')}"
            loc_resumida = (
                f" | 📍 {localizacao_txt[:30]}..."
                if len(localizacao_txt) > 30
                else f" | 📍 {localizacao_txt}"
            )

            titulo_card = f"{status_icone} {reg['placa']} - {reg['modelo']}{op_txt}{loc_resumida} | 🕒 {data_formatada}"

            with st.expander(titulo_card):
                foto_val = reg.get("foto")
                tem_foto_valida = False
                if foto_val is not None:
                    if isinstance(foto_val, memoryview):
                        foto_val = bytes(foto_val)
                    if isinstance(foto_val, bytes) and len(foto_val) > 0:
                        tem_foto_valida = True

                col_detalhes, col_foto_card = st.columns([3, 1] if tem_foto_valida else [1, 0.001])

                with col_detalhes:
                    st.write(f"**Tipo de Operação:** {reg.get('tipo_operacao', 'N/A')}")
                    st.write(f"**Responsável / Admin:** {reg['motorista_nome']}")
                    st.write(f"**Data e Hora do Registo:** {data_formatada}")
                    st.write(f"**Endereço / Localização (GPS):** {localizacao_txt}")
                    st.write(f"**KM Inspecionado:** {reg['km']} km")
                    st.write(f"**Resultado Geral:** {reg['resultado']}")

                    if reg["observacoes"]:
                        st.info(f"**Observações:** {reg['observacoes']}")

                if tem_foto_valida:
                    with col_foto_card:
                        try:
                            st.write("🖼 **Avaria:**")
                            imagem_obj = Image.open(io.BytesIO(foto_val))
                            st.image(imagem_obj, width=120)
                            with st.expander("🔍 Ampliar Foto"):
                                st.image(imagem_obj, use_container_width=True)
                        except Exception as e:
                            st.warning(f"Erro ao carregar imagem: {e}")

                itens = buscar_itens_checklist(reg["id"])
                itens_falha = [i for i in itens if i["resultado"] == "NÃO OK"]

                if itens_falha:
                    st.error("⚠ **Itens com Avaria:**")
                    for item_f in itens_falha:
                        st.write(
                            f"- **{item_f['categoria']} - {item_f['item']}**:"
                            f" {item_f['resultado']}"
                        )
                else:
                    st.success(
                        "✅ Todos os itens foram aprovados nesta vistoria."
                    )
