import datetime
import io
import json
import time
import urllib.request
from PIL import Image
import pandas as pd
import streamlit as st
from database.connection import get_connection
from views.services.cadastros_service import listar_motoristas, listar_veiculos


def obter_endereco_reverso(lat_lon_str):
    """Converte coordenadas (latitude, longitude) num endereço legível completo via Nominatim."""
    try:
        if not lat_lon_str or "," not in lat_lon_str or "Erro" in lat_lon_str or "Não" in lat_lon_str:
            return lat_lon_str

        partes = lat_lon_str.split(",")
        if len(partes) != 2:
            return lat_lon_str

        lat = partes[0].strip()
        lon = partes[1].strip()

        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        req = urllib.request.Request(
            url, headers={"User-Agent": "ControleFrotaApp/1.0"}
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
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
    localizacao_amigavel = obter_endereco_reverso(localizacao)

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
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
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
                foto_bytes,
                usuario_responsavel,
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

                val_oco = {
                    "veiculo_id": veiculo_id,
                    "motorista_id": motorista_id if motorista_id else 1,
                    "checklist_id": checklist_id,
                    "item": item,
                    "descricao": f"Avaria apontada no checklist (Local: {localizacao_amigavel}): {item}",
                    "status": "Aberto",
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

        # Captura automática do GPS via background injetado
        query_params = st.query_params
        gps_recebido = query_params.get("gps_auto", None)
        if gps_recebido and gps_recebido != "GPS Não Capturado":
            st.session_state["gps_localizacao_atual"] = gps_recebido

        # Script invisível que executa a geolocalização automaticamente em background assim que a página abre
        st.components.v1.html(
            """
            <script>
            if (navigator.geolocation) {
                const urlParams = new URLSearchParams(window.parent.location.search);
                if (!urlParams.has('gps_auto')) {
                    navigator.geolocation.getCurrentPosition(
                        function(pos) {
                            const lat = pos.coords.latitude.toFixed(6);
                            const lon = pos.coords.longitude.toFixed(6);
                            const coords = lat + "," + lon;
                            
                            const url = new URL(window.parent.location);
                            url.searchParams.set('gps_auto', coords);
                            window.parent.history.replaceState({}, '', url);
                            window.parent.location.reload();
                        },
                        function(err) {
                            const url = new URL(window.parent.location);
                            url.searchParams.set('gps_auto', 'GPS Não Capturado');
                            window.parent.history.replaceState({}, '', url);
                        },
                        { maximumAge: 0, timeout: 15000, enableHighAccuracy: true }
                    );
                }
            }
            </script>
            """,
            height=0,
        )

        with st.form("form_checklist", clear_on_submit=True):
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

            st.text_input(
                "Responsável pelo Registo", value=usuario_nome, disabled=True
            )

            km = st.number_input(
                "Quilometragem Atual (KM)*",
                min_value=int(km_anterior),
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
                    key=f"item_{cat}_{item}",
                )

            st.divider()
            st.subheader("3. Evidências e Observações")

            st.write("📸 **Fotografia da Avaria (Opcional)**")
            st.caption("Tire uma foto com a câmara ou selecione um ficheiro/imagem da galeria.")
            
            foto = st.file_uploader(
                "Carregar ou tirar foto da avaria", 
                type=["jpg", "jpeg", "png", "heic"], 
                key="foto_avaria_checklist",
                label_visibility="collapsed"
            )

            obs = st.text_area("Observações / Detalhes de problemas")

            btn_enviar = st.form_submit_button(
                "✅ Finalizar e Enviar Checklist", use_container_width=True
            )

            if btn_enviar:
                loc_final = st.session_state.get("gps_localizacao_atual", "GPS Não Capturado")
                foto_bytes = foto.getvalue() if foto is not None else None

                try:
                    salvar_checklist(
                        veiculo_id,
                        motorista_id,
                        tipo_operacao,
                        km,
                        respostas,
                        obs,
                        foto_bytes,
                        loc_final,
                        usuario_nome,
                    )
                    if "gps_localizacao_atual" in st.session_state:
                        del st.session_state["gps_localizacao_atual"]

                    st.success("Checklist registrado e salvo com sucesso no sistema!")
                    time.sleep(1)
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
                        if r["placa"]
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
                data_formatada = datetime.datetime.now().strftime(
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
                st.write(
                    f"**Tipo de Operação:** {reg.get('tipo_operacao', 'N/A')}"
                )
                st.write(f"**Responsável / Admin:** {reg['motorista_nome']}")
                st.write(f"**Data e Hora do Registro:** {data_formatada}")
                st.write(
                    f"**Endereço / Localização (GPS):** {localizacao_txt}"
                )
                st.write(f"**KM Inspecionado:** {reg['km']} km")
                st.write(f"**Resultado Geral:** {reg['resultado']}")

                if reg["observacoes"]:
                    st.info(f"**Observações:** {reg['observacoes']}")

                # EXIBIR FOTO ANEXADA (SE HOUVER)
                if reg.get("foto") is not None:
                    try:
                        st.write("---")
                        st.write("🖼 **Fotografia da Avaria Anexada:**")
                        imagem_obj = Image.open(io.BytesIO(reg["foto"]))
                        st.image(
                            imagem_obj,
                            caption=f"Veículo {reg['placa']} - Vistoria #{reg['id']}",
                            use_container_width=True,
                        )
                    except Exception:
                        st.warning("Não foi possível renderizar a imagem anexada.")

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
