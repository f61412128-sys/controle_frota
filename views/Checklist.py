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

        usuario_nome = st.session_state.get("usuario_nome", st.session_state.get("usuario", "Administrador"))
        motorista_id = st.session_state.get("motorista_id")

        # Script JS com alta prioridade e repetição contínua para capturar o GPS rapidamente
        st.components.v1.html(
            """
            <script>
            function pegarGPS() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        function(position) {
                            const lat = position.coords.latitude.toFixed(6);
                            const lon = position.coords.longitude.toFixed(6);
                            const coords = lat + ", " + lon;
                            
                            const url = new URL(window.parent.location);
                            if (url.searchParams.get('gps_auto') !== coords) {
                                url.searchParams.set('gps_auto', coords);
                                window.parent.history.replaceState({}, '', url);
                            }
                        },
                        function(error) {
                            const url = new URL(window.parent.location);
                            if (!url.searchParams.get('gps_auto') || url.searchParams.get('gps_auto').includes('Aguardando')) {
                                url.searchParams.set('gps_auto', 'Localização por Rede / Indisponível');
                                window.parent.history.replaceState({}, '', url);
                            }
                        },
                        { maximumAge: 0, timeout: 20000, enableHighAccuracy: true }
                    );
                }
            }
            pegarGPS();
            setInterval(pegarGPS, 4000);
            </script>
            """,
            height=0,
        )

        localizacao_gps = st.query_params.get(
            "gps_auto", "Aguardando sinal de GPS..."
        )

        with st.form("form_checklist", clear_on_submit=True):
            st.subheader("1. Identificação")

            veiculo_sel = st.selectbox("Selecione o Veículo*", list(mapa_v.keys()))
            veiculo_id, km_anterior = mapa_v[veiculo_sel]

            tipo_operacao = st.selectbox(
                "Tipo de Operação*",
                ["Saída (Retirada do Veículo)", "Entrada (Devolução ao Pátio)"]
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
            st.subheader("3. Evidência e Observações")

            ativar_camera = st.checkbox("📸 Deseja tirar foto de alguma avaria?")
            foto = None
            if ativar_camera:
                foto = st.camera_input("Aponte para a avaria e tire a fotografia")

            obs = st.text_area("Observações / Detalhes de problemas")

            btn_enviar = st.form_submit_button(
                "✅ Finalizar e Enviar Checklist", use_container_width=True
            )

            if btn_enviar:
                foto_bytes = foto.getvalue() if foto else None

                # ADICIONANDO PAUSA INTELIGENTE DE ATÉ 4 SEGUNDOS PARA CAPTURA DE GPS
                with st.spinner("📍 Obtendo localização exata via GPS e salvando..."):
                    tentativa = 0
                    loc_atual = st.query_params.get("gps_auto", "Aguardando sinal de GPS...")
                    
                    while "Aguardando" in loc_atual and tentativa < 8:
                        time.sleep(0.5)
                        loc_atual = st.query_params.get("gps_auto", "Aguardando sinal de GPS...")
                        tentativa += 1

                try:
                    salvar_checklist(
                        veiculo_id,
                        motorista_id,
                        tipo_operacao,
                        km,
                        respostas,
                        obs,
                        foto_bytes,
                        loc_atual,
                        usuario_nome,
                    )
                    st.success(
                        "Checklist registrado e salvo com sucesso no sistema!"
                    )
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
            apenas_pendencias = st.checkbox("⚠️ Apenas com Pendências")

        registros_filtrados = registros
        if filtro_veiculo != "Todos":
            registros_filtrados = [
                r
                for r in registros_filtrados
                if f"{r['placa']} - {r['modelo']}" == filtro_veiculo
            ]
        if apenas_pendencias:
            registros_filtrados = [
                r for r in registros_filtrados if r["resultado"] == "Com pendências"
            ]

        st.write(f"Exibindo **{len(registros_filtrados)}** registos:")

        for reg in registros_filtrados:
            status_icone = (
                "🔴" if reg["resultado"] == "Com pendências" else "🟢"
            )
            data_formatada = reg.get("created_at", "Data N/A")
            loc_txt = (
                f" | 📍 {reg['localizacao']}"
                if reg.get("localizacao")
                else ""
            )
            op_txt = f" | 🔄 {reg.get('tipo_operacao', 'N/A')}"

            titulo_card = (
                f"{status_icone} {reg['placa']} - {reg['modelo']}{op_txt}{loc_txt} |"
                f" {data_formatada}"
            )

            with st.expander(titulo_card):
                st.write(f"**Tipo de Operação:** {reg.get('tipo_operacao', 'N/A')}")
                st.write(f"**Responsável / Admin:** {reg['motorista_nome']}")
                st.write(
                    f"**Localização Registrada (GPS):**"
                    f" {reg.get('localizacao', 'Não informada')}"
                )
                st.write(f"**KM Inspecionado:** {reg['km']} km")
                st.write(f"**Resultado Geral:** {reg['resultado']}")

                if reg["observacoes"]:
                    st.info(f"**Observações:** {reg['observacoes']}")

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
                    st.success("✅ Todos os itens foram aprovados nesta vistoria.")
