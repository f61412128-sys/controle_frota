import datetime
import pandas as pd
import streamlit as st
from database.connection import get_connection


def render_cards_veiculos_estilizados(df_veiculos):
    if df_veiculos.empty:
        st.info("Nenhum veículo registado nesta secção.")
        return

    st.markdown(
        """
        <style>
        .veiculo-card {
            background-color: #111827;
            border: 1px solid #1f2937;
            border-left: 4px solid #3b82f6;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 12px;
        }
        .veiculo-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .veiculo-placa {
            font-size: 15px;
            font-weight: bold;
            color: #ffffff;
        }
        .badge-disponivel {
            background-color: #065f46;
            color: #34d399;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-indisponivel {
            background-color: #7f1d1d;
            color: #f87171;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .veiculo-info {
            font-size: 13px;
            color: #9ca3af;
            margin-bottom: 4px;
        }
        .veiculo-info span {
            color: #f3f4f6;
            font-weight: 500;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    for _, row in df_veiculos.iterrows():
        placa = str(row.get("placa", "N/A"))
        modelo = str(row.get("modelo", "N/A"))
        tipo = str(row.get("tipo_propriedade", row.get("tipo", "N/A")))
        consumo_medio = row.get("consumo_medio", "Não calculado")

        status_disp = row.get("status_disponibilidade", "Disponível")
        ultimo_resp = row.get("ultimo_responsavel", "Sem registo")
        tipo_mov = row.get("ultimo_tipo_movimento", "")
        data_hora_chk = row.get("ultimo_data_hora", "N/A")
        endereco_chk = row.get("ultimo_endereco", "Não informado")

        if status_disp == "Disponível":
            badge_html = (
                '<span class="badge-disponivel">🟢 Disponível </span>'
            )
        else:
            badge_html = '<span class="badge-indisponivel">🔴 Em Uso / Indisponível</span>'

        mov_text = f" ({tipo_mov})" if tipo_mov else ""

        st.markdown(
            f"""
            <div class="veiculo-card">
                <div class="veiculo-header">
                    <span class="veiculo-placa">🚗 {placa} - {modelo}</span>
                    {badge_html}
                </div>
                <div class="veiculo-info">Tipo: <span>{tipo}</span></div>
                <div class="veiculo-info">Consumo Médio: <span>{consumo_medio}</span></div>
                <div class="veiculo-info">Último Registo{mov_text}: <span>{ultimo_resp}</span></div>
                <div class="veiculo-info">Data e Hora: <span>{data_hora_chk}</span></div>
                <div class="veiculo-info">Endereço: <span>{endereco_chk}</span></div>
            </div>
        """,
            unsafe_allow_html=True,
        )


def ler_tabela_direta(query):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        if rows:
            cols = [desc[0] for desc in cursor.description]
            df = pd.DataFrame(rows, columns=cols)
        else:
            df = pd.DataFrame()
        cursor.close()
        conn.close()
        return df
    except Exception as e:
        conn.close()
        return pd.DataFrame()


def render_dashboard(contar_registros_fn=None):
    st.title("📊 Painel Geral da Frota")

    df_tables = ler_tabela_direta(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
    )
    tabelas_existentes = (
        df_tables["table_name"].tolist() if not df_tables.empty else []
    )

    df_veiculos = (
        ler_tabela_direta("SELECT * FROM veiculos")
        if "veiculos" in tabelas_existentes
        else pd.DataFrame()
    )
    df_manutencoes = (
        ler_tabela_direta("SELECT * FROM manutencoes")
        if "manutencoes" in tabelas_existentes
        else pd.DataFrame()
    )
    df_motoristas = (
        ler_tabela_direta("SELECT * FROM motoristas")
        if "motoristas" in tabelas_existentes
        else pd.DataFrame()
    )
    df_usuarios = (
        ler_tabela_direta("SELECT * FROM usuarios")
        if "usuarios" in tabelas_existentes
        else pd.DataFrame()
    )

    # Carregar dados de abastecimentos
    df_abastecimentos = pd.DataFrame()
    for t_abast in ["abastecimentos", "abastecimento", "combustivel"]:
        if t_abast in tabelas_existentes:
            df_temp = ler_tabela_direta(f"SELECT * FROM {t_abast}")
            if not df_temp.empty:
                df_abastecimentos = df_temp
                break

    df_checklists = pd.DataFrame()
    for t in ["checklists", "checklist", "historico_checklists", "inspecoes"]:
        if t in tabelas_existentes:
            df_temp = ler_tabela_direta(f"SELECT * FROM {t}")
            if not df_temp.empty:
                df_checklists = df_temp
                break

    if df_checklists.empty:
        for t in tabelas_existentes:
            df_temp = ler_tabela_direta(f"SELECT * FROM {t}")
            if not df_temp.empty and any(
                k in t.lower() for k in ["check", "insp", "vist"]
            ):
                df_checklists = df_temp
                break

    # Cruzamento de checklists e cálculo de consumo por veículo
    if not df_veiculos.empty:
        status_list = []
        resp_list = []
        tipo_mov_list = []
        data_hora_list = []
        endereco_list = []
        consumo_list = []

        for _, v_row in df_veiculos.iterrows():
            v_id = v_row.get("id")
            v_placa = str(v_row.get("placa", "")).strip().upper()

            consumo_str = "Não calculado"
            if not df_abastecimentos.empty:
                mask_abast = pd.Series(False, index=df_abastecimentos.index)
                if "veiculo_id" in df_abastecimentos.columns and v_id is not None:
                    mask_abast |= df_abastecimentos["veiculo_id"] == v_id
                if "placa" in df_abastecimentos.columns and v_placa:
                    mask_abast |= (
                        df_abastecimentos["placa"]
                        .astype(str)
                        .str.upper()
                        .str.strip()
                        == v_placa
                    )

                df_v_abast = df_abastecimentos[mask_abast]
                if not df_v_abast.empty:
                    col_km = next(
                        (
                            c
                            for c in [
                                "km",
                                "quilometragem",
                                "odometro",
                                "km_atual",
                            ]
                            if c in df_v_abast.columns
                        ),
                        None,
                    )
                    col_litros = next(
                        (
                            c
                            for c in [
                                "litros",
                                "quantidade",
                                "qtd_litros",
                                "volume",
                            ]
                            if c in df_v_abast.columns
                        ),
                        None,
                    )

                    if col_km and col_litros:
                        try:
                            df_v_abast = df_v_abast.sort_values(by=col_km)
                            km_vals = pd.to_numeric(
                                df_v_abast[col_km], errors="coerce"
                            ).dropna()
                            litros_vals = pd.to_numeric(
                                df_v_abast[col_litros], errors="coerce"
                            ).dropna()
                            if len(km_vals) >= 2 and litros_vals.sum() > 0:
                                diff_km = km_vals.iloc[-1] - km_vals.iloc[0]
                                total_l = litros_vals.sum()
                                if diff_km > 0:
                                    media = diff_km / total_l
                                    consumo_str = f"{media:.2f} km/L"
                        except Exception:
                            pass

                    if consumo_str == "Não calculado":
                        for c_med in [
                            "consumo_medio",
                            "media_km_l",
                            "consumo",
                        ]:
                            if c_med in df_v_abast.columns:
                                val_m = df_v_abast[c_med].dropna()
                                if not val_m.empty:
                                    consumo_str = (
                                        f"{float(val_m.iloc[-1]):.2f} km/L"
                                    )
                                    break

            consumo_list.append(consumo_str)

            df_chk_veiculo = pd.DataFrame()
            if (
                not df_checklists.empty
                and "veiculo_id" in df_checklists.columns
                and v_id is not None
            ):
                mask = df_checklists["veiculo_id"] == v_id
                df_chk_veiculo = df_checklists[mask]

            if not df_chk_veiculo.empty:
                col_data = None
                for c in [
                    "data_hora",
                    "created_at",
                    "data",
                    "data_checklist",
                    "timestamp",
                ]:
                    if c in df_chk_veiculo.columns:
                        col_data = c
                        break

                if col_data:
                    try:
                        df_chk_veiculo = df_chk_veiculo.sort_values(
                            by=col_data, ascending=False
                        )
                    except Exception:
                        pass

                ult_chk = df_chk_veiculo.iloc[0]
                raw_data = ult_chk.get(col_data) if col_data else None
                if isinstance(raw_data, datetime.datetime):
                    data_formatada = raw_data.strftime("%d/%m/%Y %H:%M")
                elif raw_data and str(raw_data).strip() not in [
                    "",
                    "None",
                    "NaT",
                ]:
                    data_str = str(raw_data).strip()
                    data_formatada = (
                        data_str[:16].replace("T", " ")
                        if len(data_str) >= 16
                        else data_str
                    )
                else:
                    data_formatada = "N/A"

                endereco_chk = "Não informado"
                for col_loc in ["localizacao", "endereco", "gps"]:
                    if col_loc in ult_chk and pd.notna(ult_chk[col_loc]):
                        endereco_chk = str(ult_chk[col_loc])
                        break

                resp = "Administrador / Sistema"
                for col_resp in [
                    "responsavel",
                    "usuario_responsavel",
                    "nome_responsavel",
                ]:
                    if col_resp in ult_chk and pd.notna(ult_chk[col_resp]):
                        resp = str(ult_chk[col_resp])
                        break

                tipo_mov = ""
                for col_tipo in [
                    "tipo_operacao",
                    "tipo_movimento",
                    "operacao",
                    "movimento",
                    "fluxo",
                ]:
                    if col_tipo in ult_chk and pd.notna(ult_chk[col_tipo]):
                        tipo_mov = str(ult_chk[col_tipo])
                        break

                tipo_mov_lower = tipo_mov.lower()
                if any(
                    k in tipo_mov_lower for k in ["saida", "retirada", "uso"]
                ):
                    status_disp = "Indisponível"
                else:
                    status_disp = "Disponível"

                status_list.append(status_disp)
                resp_list.append(resp)
                tipo_mov_list.append(
                    tipo_mov if tipo_mov else "Registo Geral"
                )
                data_hora_list.append(data_formatada)
                endereco_list.append(endereco_chk)
            else:
                status_list.append("Disponível")
                resp_list.append("Sem checklist recente")
                tipo_mov_list.append("")
                data_hora_list.append("N/A")
                endereco_list.append("Não informado")

        df_veiculos["status_disponibilidade"] = status_list
        df_veiculos["ultimo_responsavel"] = resp_list
        df_veiculos["ultimo_tipo_movimento"] = tipo_mov_list
        df_veiculos["ultimo_data_hora"] = data_hora_list
        df_veiculos["ultimo_endereco"] = endereco_list
        df_veiculos["consumo_medio"] = consumo_list
    else:
        df_veiculos["status_disponibilidade"] = "Disponível"
        df_veiculos["ultimo_responsavel"] = "N/A"
        df_veiculos["ultimo_tipo_movimento"] = ""
        df_veiculos["ultimo_data_hora"] = "N/A"
        df_veiculos["ultimo_endereco"] = "Não informado"
        df_veiculos["consumo_medio"] = "Não calculado"

    custo_total_manut = 0.0
    if not df_manutencoes.empty:
        for col_val in ["valor", "custo", "preco", "valor_total"]:
            if col_val in df_manutencoes.columns:
                try:
                    valores_limpos = pd.to_numeric(
                        df_manutencoes[col_val]
                        .astype(str)
                        .str.replace("R$", "", regex=True)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", ".", regex=False),
                        errors="coerce",
                    )
                    custo_total_manut = float(valores_limpos.sum())
                    break
                except Exception:
                    pass

    total_venc_contratos = 0
    df_contratos = pd.DataFrame()
    for t_c in ["contratos", "locacoes", "gestao_contratos"]:
        if t_c in tabelas_existentes:
            df_temp = ler_tabela_direta(f"SELECT * FROM {t_c}")
            if not df_temp.empty:
                df_contratos = df_temp
                break

    if not df_contratos.empty:
        col_venc = None
        for c in [
            "data_fim",
            "vencimento",
            "termino_contrato",
            "data_termino",
            "vencimento_contrato",
        ]:
            if c in df_contratos.columns:
                col_venc = c
                break
        if col_venc:
            try:
                hoje = pd.Timestamp.now().normalize()
                datas_venc = pd.to_datetime(
                    df_contratos[col_venc], errors="coerce"
                )
                limite = hoje + pd.Timedelta(days=30)
                total_venc_contratos = int(
                    ((datas_venc >= hoje) & (datas_venc <= limite)).sum()
                    + (datas_venc < hoje).sum()
                )
            except Exception:
                pass

    df_alugados = pd.DataFrame()
    df_proprios = pd.DataFrame()
    if not df_veiculos.empty:
        col_alvo = None
        for c in ["tipo_propriedade", "tipo", "posse", "categoria"]:
            if c in df_veiculos.columns:
                col_alvo = c
                break

        if col_alvo:
            mask_alug = (
                df_veiculos[col_alvo]
                .astype(str)
                .str.lower()
                .str.contains("alugado|terceirizado|locado|terceiro", na=False)
            )
            df_alugados = df_veiculos[mask_alug].copy()
            df_proprios = df_veiculos[~mask_alug].copy()
        else:
            df_proprios = df_veiculos.copy()

    total_veiculos = len(df_veiculos)
    total_proprios = len(df_proprios)
    total_alugados = len(df_alugados)
    total_motoristas = len(df_motoristas) if not df_motoristas.empty else 0
    total_manut = len(df_manutencoes)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚚 Frota Total", total_veiculos)
    c2.metric("🏢 Próprios", total_proprios)
    c3.metric("📋 Alugados", total_alugados)
    c4.metric("🛠 Em Manutenção", total_manut)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("💰 Custo Manutenções", f"R$ {custo_total_manut:,.2f}")
    c6.metric("👨‍✈️ Motoristas", total_motoristas)
    c7.metric("⚠ Ocorrências", 0)
    c8.metric("📄 Venc. Contratos", total_venc_contratos)

    st.divider()

    # Criação das abas, incluindo a nova aba de Consumo
    (
        tab_contratos,
        tab_consumo,
        tab_rodizio,
        tab_manut,
        tab_pendencias,
    ) = st.tabs([
        "📄 Gestão de Contratos & Frota",
        "⛽ Consumo & Abastecimentos",
        "🚘 Rodízio Hoje",
        "🛠 Manutenções Recentes",
        "⚠ Ocorrências",
    ])

    with tab_contratos:
        sub_alug, sub_prop = st.tabs(
            ["📋 Alugados / Terceirizados", "🏢 Próprios"]
        )
        with sub_alug:
            render_cards_veiculos_estilizados(df_alugados)
        with sub_prop:
            render_cards_veiculos_estilizados(df_proprios)

    with tab_consumo:
        st.markdown("##### 📊 Indicadores de Consumo e Combustível")

        # Cálculos de consumo do dia e do mês se houver dados
        custo_dia = 0.0
        litros_dia = 0.0
        custo_mes = 0.0
        litros_mes = 0.0

        if not df_abastecimentos.empty:
            col_data_abast = next(
                (
                    c
                    for c in [
                        "data",
                        "data_abastecimento",
                        "created_at",
                        "data_hora",
                    ]
                    if c in df_abastecimentos.columns
                ),
                None,
            )
            col_valor_abast = next(
                (
                    c
                    for c in [
                        "valor",
                        "valor_total",
                        "custo",
                        "preco_total",
                    ]
                    if c in df_abastecimentos.columns
                ),
                None,
            )
            col_litros_abast = next(
                (
                    c
                    for c in [
                        "litros",
                        "quantidade",
                        "qtd_litros",
                        "volume",
                    ]
                    if c in df_abastecimentos.columns
                ),
                None,
            )

            if col_data_abast:
                try:
                    df_abastecimentos["_dt"] = pd.to_datetime(
                        df_abastecimentos[col_data_abast], errors="coerce"
                    )
                    hoje_ts = pd.Timestamp.now().normalize()
                    mes_atual = hoje_ts.month
                    ano_atual = hoje_ts.year

                    mask_dia = df_abastecimentos["_dt"].dt.normalize() == hoje_ts
                    mask_mes = (df_abastecimentos["_dt"].dt.month == mes_atual) & (
                        df_abastecimentos["_dt"].dt.year == ano_atual
                    )

                    if col_valor_abast:
                        vals = pd.to_numeric(
                            df_abastecimentos[col_valor_abast]
                            .astype(str)
                            .str.replace("R$", "", regex=True)
                            .str.replace(",", ".", regex=False),
                            errors="coerce",
                        )
                        custo_dia = float(vals[mask_dia].sum())
                        custo_mes = float(vals[mask_mes].sum())

                    if col_litros_abast:
                        lits = pd.to_numeric(
                            df_abastecimentos[col_litros_abast], errors="coerce"
                        )
                        litros_dia = float(lits[mask_dia].sum())
                        litros_mes = float(lits[mask_mes].sum())
                except Exception:
                    pass

        # Métricas rápidas no topo da aba de consumo
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("⛽ Litros Hoje", f"{litros_dia:.1f} L")
        m2.metric("💵 Gasto Hoje", f"R$ {custo_dia:,.2f}")
        m3.metric("📅 Litros no Mês", f"{litros_mes:.1f} L")
        m4.metric("💰 Gasto no Mês", f"R$ {custo_mes:,.2f}")

        st.divider()
        st.markdown("##### 🚗 Desempenho de Consumo por Veículo")

        if df_veiculos.empty:
            st.info("Nenhum veículo registado.")
        else:
            # Reutiliza o estilo dos cartões para exibir o consumo detalhado por carro
            st.markdown(
                """
                <style>
                .consumo-card {
                    background-color: #111827;
                    border: 1px solid #1f2937;
                    border-left: 4px solid #10b981;
                    padding: 12px 16px;
                    border-radius: 8px;
                    margin-bottom: 12px;
                }
                .consumo-header {
                    font-size: 15px;
                    font-weight: bold;
                    color: #ffffff;
                    margin-bottom: 8px;
                }
                .consumo-info {
                    font-size: 13px;
                    color: #9ca3af;
                    margin-bottom: 4px;
                }
                .consumo-info span {
                    color: #f3f4f6;
                    font-weight: 500;
                }
                </style>
            """,
                unsafe_allow_html=True,
            )

            for _, row in df_veiculos.iterrows():
                placa = str(row.get("placa", "N/A"))
                modelo = str(row.get("modelo", "N/A"))
                consumo = row.get("consumo_medio", "Não calculado")

                # Calcula total gasto neste veículo específico se houver tabela de abastecimento
                gasto_veiculo = 0.0
                litros_veiculo = 0.0
                km_percorrido = "Não registado"

                if not df_abastecimentos.empty:
                    v_id = row.get("id")
                    mask_v = pd.Series(False, index=df_abastecimentos.index)
                    if "veiculo_id" in df_abastecimentos.columns and v_id is not None:
                        mask_v |= df_abastecimentos["veiculo_id"] == v_id
                    if "placa" in df_abastecimentos.columns:
                        mask_v |= (
                            df_abastecimentos["placa"]
                            .astype(str)
                            .str.upper()
                            .str.strip()
                            == placa.upper()
                        )

                    df_abast_v = df_abastecimentos[mask_v]
                    if not df_abast_v.empty:
                        if col_valor_abast:
                            gasto_veiculo = float(
                                pd.to_numeric(
                                    df_abast_v[col_valor_abast]
                                    .astype(str)
                                    .str.replace("R$", "", regex=True)
                                    .str.replace(",", ".", regex=False),
                                    errors="coerce",
                                ).sum()
                            )
                        if col_litros_abast:
                            litros_veiculo = float(
                                pd.to_numeric(
                                    df_abast_v[col_litros_abast], errors="coerce"
                                ).sum()
                            )
                        col_km = next(
                            (
                                c
                                for c in [
                                    "km",
                                    "quilometragem",
                                    "odometro",
                                    "km_atual",
                                ]
                                if c in df_abast_v.columns
                            ),
                            None,
                        )
                        if col_km:
                            k_vals = pd.to_numeric(
                                df_abast_v[col_km], errors="coerce"
                            ).dropna()
                            if len(k_vals) >= 2:
                                km_percorrido = (
                                    f"{k_vals.iloc[-1] - k_vals.iloc[0]} km"
                                )

                st.markdown(
                    f"""
                    <div class="consumo-card">
                        <div class="consumo-header">⛽ {placa} - {modelo}</div>
                        <div class="consumo-info">Consumo Médio: <span>{consumo}</span></div>
                        <div class="consumo-info">KM Percorrido (Base Abastecimentos): <span>{km_percorrido}</span></div>
                        <div class="consumo-info">Total Litros Abastecidos: <span>{litros_veiculo:.1f} L</span></div>
                        <div class="consumo-info">Gasto Acumulado: <span>R$ {gasto_veiculo:,.2f}</span></div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )

    with tab_rodizio:
        st.markdown("##### Consulta de Rodízio (SP)")
        hoje_idx = datetime.datetime.now().weekday()
        regras = {
            0: "Placas 1 e 2",
            1: "Placas 3 e 4",
            2: "Placas 5 e 6",
            3: "Placas 7 e 8",
            4: "Placas 9 e 0",
        }
        if hoje_idx < 5:
            st.warning(f"🚫 Restrição hoje: {regras.get(hoje_idx)}")
        else:
            st.success("✅ Sem restrição no fim de semana.")

    with tab_manut:
        if not df_manutencoes.empty:
            st.dataframe(
                df_manutencoes, use_container_width=True, hide_index=True
            )
        else:
            st.info("Sem manutenções recentes registadas.")

    with tab_pendencias:
        st.success("Nenhuma ocorrência pendente!")
