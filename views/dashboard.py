import datetime
import io
import pandas as pd
import streamlit as st
from PIL import Image
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

    df_ocorrencias = pd.DataFrame()
    if "ocorrencias" in tabelas_existentes:
        df_oc_cols = ler_tabela_direta("SELECT * FROM ocorrencias LIMIT 0")
        cols_oc = df_oc_cols.columns.tolist() if not df_oc_cols.empty else []

        foto_oc_col = next(
            (
                c
                for c in ["foto", "imagem", "comprovante", "anexo"]
                if c in cols_oc
            ),
            None,
        )
        has_chk_id = "checklist_id" in cols_oc
        has_chk_table = "checklists" in tabelas_existentes

        if foto_oc_col and has_chk_id and has_chk_table:
            query_ocorr = f"""
                SELECT o.*, COALESCE(o.{foto_oc_col}, c.foto) as foto, v.placa, v.modelo 
                FROM ocorrencias o
                LEFT JOIN checklists c ON o.checklist_id = c.id
                LEFT JOIN veiculos v ON o.veiculo_id = v.id
                ORDER BY o.id DESC
            """
        elif foto_oc_col:
            query_ocorr = f"""
                SELECT o.*, o.{foto_oc_col} as foto, v.placa, v.modelo 
                FROM ocorrencias o
                LEFT JOIN veiculos v ON o.veiculo_id = v.id
                ORDER BY o.id DESC
            """
        elif has_chk_id and has_chk_table:
            query_ocorr = """
                SELECT o.*, c.foto as foto, v.placa, v.modelo 
                FROM ocorrencias o
                LEFT JOIN checklists c ON o.checklist_id = c.id
                LEFT JOIN veiculos v ON o.veiculo_id = v.id
                ORDER BY o.id DESC
            """
        else:
            query_ocorr = """
                SELECT o.*, v.placa, v.modelo 
                FROM ocorrencias o
                LEFT JOIN veiculos v ON o.veiculo_id = v.id
                ORDER BY o.id DESC
            """
        df_ocorrencias = ler_tabela_direta(query_ocorr)
    else:
        for t_oc in ["ocorrencia", "incidentes", "problemas"]:
            if t_oc in tabelas_existentes:
                df_ocorrencias = ler_tabela_direta(f"SELECT * FROM {t_oc}")
                break

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
                    "created_at",
                    "data_hora",
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
                    raw_data_ajustado = raw_data + datetime.timedelta(hours=3)
                    data_formatada = raw_data_ajustado.strftime("%d/%m/%Y %H:%M")
                elif raw_data and str(raw_data).strip() not in [
                    "",
                    "None",
                    "NaT",
                ]:
                    data_str = str(raw_data).strip()
                    try:
                        dt_parsed = pd.to_datetime(data_str)
                        dt_ajustado = dt_parsed + pd.Timedelta(hours=3)
                        data_formatada = dt_ajustado.strftime("%d/%m/%Y %H:%M")
                    except Exception:
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
    for t_c in [
        "contratos",
        "locacoes",
        "gestao_contratos",
        "veiculos_contratos",
    ]:
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
            "data_vencimento",
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

    if total_venc_contratos == 0 and not df_veiculos.empty:
        col_venc_v = None
        for c in [
            "vencimento_contrato",
            "data_fim_contrato",
            "fim_contrato",
            "vencimento",
            "data_vencimento",
        ]:
            if c in df_veiculos.columns:
                col_venc_v = c
                break
        if col_venc_v:
            try:
                hoje = pd.Timestamp.now().normalize()
                datas_venc = pd.to_datetime(
                    df_veiculos[col_venc_v], errors="coerce"
                )
                limite = hoje + pd.Timedelta(days=30)
                total_venc_contratos = int(
                    ((datas_venc >= hoje) & (datas_venc <= limite)).sum()
                    + (datas_venc < hoje).sum()
                )
            except Exception:
                pass

    total_ocorrencias = len(df_ocorrencias) if not df_ocorrencias.empty else 0

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
    c6.metric("👨 Motoristas", total_motoristas)
    c7.metric("⚠ Ocorrências", total_ocorrencias)
    c8.metric("📄 Venc. Contratos", total_venc_contratos)

    st.divider()

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

        custo_dia = 0.0
        litros_dia = 0.0
        custo_mes = 0.0
        litros_mes = 0.0

        col_data_abast = None
        col_valor_abast = None
        col_litros_abast = None
        col_comprovante_abast = None

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
            col_comprovante_abast = next(
                (
                    c
                    for c in [
                        "comprovante",
                        "foto",
                        "recibo",
                        "imagem",
                        "arquivo",
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

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("⛽ Litros Hoje", f"{litros_dia:.1f} L")
        m2.metric("💵 Gasto Hoje", f"R$ {custo_dia:,.2f}")
        m3.metric("📅 Litros no Mês", f"{litros_mes:.1f} L")
        m4.metric("💰 Gasto no Mês", f"R$ {custo_mes:,.2f}")

        st.divider()
        st.markdown(
            "##### 🚗 Histórico de Abastecimentos e Comprovantes por Veículo"
        )

        if df_veiculos.empty:
            st.info("Nenhum veículo registado.")
        else:
            st.markdown(
                """
                <style>
                .abast-card {
                    background-color: #111827;
                    border: 1px solid #1f2937;
                    border-left: 4px solid #10b981;
                    padding: 12px 16px;
                    border-radius: 8px;
                    margin-bottom: 12px;
                }
                .abast-header {
                    font-size: 15px;
                    font-weight: bold;
                    color: #ffffff;
                    margin-bottom: 8px;
                }
                .abast-info {
                    font-size: 13px;
                    color: #9ca3af;
                    margin-bottom: 4px;
                }
                .abast-info span {
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
                v_id = row.get("id")

                df_abast_v = pd.DataFrame()
                if not df_abastecimentos.empty:
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

                if df_abast_v.empty:
                    st.markdown(
                        f"""
                        <div class="abast-card">
                            <div class="abast-header">⛽ {placa} - {modelo}</div>
                            <div class="abast-info">Nenhum registo de abastecimento para este veículo.</div>
                        </div>
                    """,
                        unsafe_allow_html=True,
                    )
                else:
                    for _, ab_row in df_abast_v.iterrows():
                        data_ab = (
                            str(ab_row.get(col_data_abast, "N/A"))
                            if col_data_abast
                            else "N/A"
                        )
                        try:
                            if col_data_abast and pd.notna(ab_row.get(col_data_abast)):
                                dt_ab = pd.to_datetime(ab_row.get(col_data_abast))
                                dt_ab_ajustado = dt_ab + pd.Timedelta(hours=3)
                                data_ab = dt_ab_ajustado.strftime("%d/%m/%Y %H:%M")
                        except Exception:
                            pass

                        litros_ab = ab_row.get(col_litros_abast, 0) if col_litros_abast else 0
                        valor_ab = ab_row.get(col_valor_abast, 0) if col_valor_abast else 0
                        
                        col_km_item = next(
                            (c for c in ["km", "quilometragem", "odometro", "km_atual"] if c in ab_row),
                            None
                        )
                        km_ab = ab_row.get(col_km_item, "N/A") if col_km_item else "N/A"

                        # Renderiza cada abastecimento com os seus dados e a respetiva foto dentro do card
                        with st.container():
                            st.markdown(
                                f"""
                                <div class="abast-card">
                                    <div class="abast-header">⛽ {placa} - {modelo}</div>
                                    <div class="abast-info">Data e Hora: <span>{data_ab}</span></div>
                                    <div class="abast-info">Quilometragem: <span>{km_ab} km</span></div>
                                    <div class="abast-info">Litros: <span>{litros_ab} L</span></div>
                                    <div class="abast-info">Valor: <span>R$ {valor_ab}</span></div>
                                </div>
                            """,
                                unsafe_allow_html=True,
                            )

                            if col_comprovante_abast:
                                comprovante_img = ab_row.get(col_comprovante_abast)
                                if comprovante_img is not None:
                                    try:
                                        if isinstance(comprovante_img, memoryview):
                                            comprovante_img = bytes(comprovante_img)

                                        if isinstance(comprovante_img, bytes):
                                            if len(comprovante_img) > 0:
                                                img_obj = Image.open(io.BytesIO(comprovante_img))
                                                st.image(
                                                    img_obj,
                                                    caption=f"🧾 Comprovante ({data_ab}) - Clique para ampliar",
                                                    width=140,
                                                )
                                        else:
                                            val_comp_str = str(comprovante_img).strip()
                                            if val_comp_str and val_comp_str.lower() not in ["none", "nan", "nat", ""]:
                                                st.image(
                                                    comprovante_img,
                                                    caption=f"🧾 Comprovante ({data_ab}) - Clique para ampliar",
                                                    width=140,
                                                )
                                    except Exception:
                                        pass

    with tab_rodizio:
        st.markdown("##### 🚘 Consulta de Rodízio de Veículos (SP)")
        hoje_idx = datetime.datetime.now().weekday()
        regras = {
            0: "Placas finais 1 e 2",
            1: "Placas finais 3 e 4",
            2: "Placas finais 5 e 6",
            3: "Placas finais 7 e 8",
            4: "Placas finais 9 e 0",
        }

        st.markdown(
            """
            <style>
            .rodizio-card {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-left: 4px solid #f59e0b;
                padding: 14px 16px;
                border-radius: 8px;
                margin-bottom: 12px;
            }
            .rodizio-title {
                font-size: 15px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 6px;
            }
            .rodizio-desc {
                font-size: 13px;
                color: #9ca3af;
            }
            .rodizio-desc span {
                color: #f3f4f6;
                font-weight: 500;
            }
            </style>
        """,
            unsafe_allow_html=True,
        )

        if hoje_idx < 5:
            restricao_hoje = regras.get(hoje_idx)
            st.markdown(
                f"""
                <div class="rodizio-card">
                    <div class="rodizio-title">🚫 Restrição Ativa Hoje</div>
                    <div class="rodizio-desc">Veículos afetados: <span>{restricao_hoje}</span></div>
                </div>
            """,
                unsafe_allow_html=True,
            )

            if not df_veiculos.empty:
                st.markdown("##### Veículos da Frota com Rodízio Hoje:")
                digitos_alvo = []
                if hoje_idx == 0:
                    digitos_alvo = ("1", "2")
                elif hoje_idx == 1:
                    digitos_alvo = ("3", "4")
                elif hoje_idx == 2:
                    digitos_alvo = ("5", "6")
                elif hoje_idx == 3:
                    digitos_alvo = ("7", "8")
                elif hoje_idx == 4:
                    digitos_alvo = ("9", "0")

                df_rodizio_veiculos = df_veiculos[
                    df_veiculos["placa"]
                    .astype(str)
                    .str.endswith(digitos_alvo, na=False)
                ]
                render_cards_veiculos_estilizados(df_rodizio_veiculos)
        else:
            st.markdown(
                """
                <div class="rodizio-card" style="border-left-color: #10b981;">
                    <div class="rodizio-title">✅ Fim de Semana</div>
                    <div class="rodizio-desc">Não há restrição de rodízio municipal hoje para nenhum veículo.</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

    with tab_manut:
        st.markdown("##### 🛠 Histórico de Manutenções Recentes")
        if not df_manutencoes.empty:
            st.markdown(
                """
                <style>
                .manut-card {
                    background-color: #111827;
                    border: 1px solid #1f2937;
                    border-left: 4px solid #ef4444;
                    padding: 12px 16px;
                    border-radius: 8px;
                    margin-bottom: 12px;
                }
                .manut-header {
                    font-size: 15px;
                    font-weight: bold;
                    color: #ffffff;
                    margin-bottom: 6px;
                }
                .manut-info {
                    font-size: 13px;
                    color: #9ca3af;
                    margin-bottom: 4px;
                }
                .manut-info span {
                    color: #f3f4f6;
                    font-weight: 500;
                }
                </style>
            """,
                unsafe_allow_html=True,
            )

            for _, row in df_manutencoes.iterrows():
                m_desc = row.get(
                    "descricao",
                    row.get("servico", row.get("tipo_manutencao", "Manutenção")),
                )
                m_custo = row.get(
                    "valor", row.get("custo", row.get("preco", "0.00"))
                )
                m_data = row.get(
                    "data", row.get("data_manutencao", row.get("created_at", "N/A"))
                )
                m_oficina = row.get("oficina", row.get("fornecedor", "Não informada"))

                st.markdown(
                    f"""
                    <div class="manut-card">
                        <div class="manut-header">🔧 {m_desc}</div>
                        <div class="manut-info">Oficina / Fornecedor: <span>{m_oficina}</span></div>
                        <div class="manut-info">Custo: <span>R$ {m_custo}</span></div>
                        <div class="manut-info">Data: <span>{m_data}</span></div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("Sem manutenções recentes registadas.")

    with tab_pendencias:
        st.markdown("##### ⚠ Registo de Ocorrências e Incidentes")
        if not df_ocorrencias.empty:
            st.markdown(
                """
                <style>
                .ocorr-card {
                    background-color: #111827;
                    border: 1px solid #1f2937;
                    border-left: 4px solid #eab308;
                    padding: 12px 16px;
                    border-radius: 8px;
                    margin-bottom: 12px;
                }
                .ocorr-header {
                    font-size: 15px;
                    font-weight: bold;
                    color: #ffffff;
                    margin-bottom: 6px;
                }
                .ocorr-info {
                    font-size: 13px;
                    color: #9ca3af;
                    margin-bottom: 4px;
                }
                .ocorr-info span {
                    color: #f3f4f6;
                    font-weight: 500;
                }
                </style>
            """,
                unsafe_allow_html=True,
            )

            for _, row in df_ocorrencias.iterrows():
                oc_desc = row.get(
                    "descricao",
                    row.get("titulo", row.get("tipo_ocorrencia", "Ocorrência")),
                )
                oc_status = row.get("status", "Pendente")
                oc_data = row.get("data", row.get("created_at", "N/A"))
                oc_resp = row.get("responsavel", row.get("motorista", "N/A"))

                placa_oc = row.get("placa", "")
                modelo_oc = row.get("modelo", "")
                veiculo_info = (
                    f" - {placa_oc} ({modelo_oc})" if placa_oc else ""
                )
                foto_oc = row.get("foto", None)

                st.markdown(
                    f"""
                    <div class="ocorr-card">
                        <div class="ocorr-header">⚠️ {oc_desc}{veiculo_info}</div>
                        <div class="ocorr-info">Status: <span>{oc_status}</span></div>
                        <div class="ocorr-info">Responsável: <span>{oc_resp}</span></div>
                        <div class="ocorr-info">Data: <span>{oc_data}</span></div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )

                if foto_oc is not None:
                    try:
                        if isinstance(foto_oc, memoryview):
                            foto_oc = bytes(foto_oc)

                        if isinstance(foto_oc, bytes):
                            if len(foto_oc) > 0:
                                imagem_obj = Image.open(io.BytesIO(foto_oc))
                                st.image(
                                    imagem_obj,
                                    caption="🔍 Evidência / Foto da Ocorrência - Clique para ampliar",
                                    width=120,
                                )
                        else:
                            val_str = str(foto_oc).strip()
                            if val_str and val_str.lower() not in ["none", "nan", "nat", ""]:
                                st.image(
                                    foto_oc,
                                    caption="🔍 Evidência / Foto da Ocorrência - Clique para ampliar",
                                    width=120,
                                )
                    except Exception:
                        pass
        else:
            st.success(
                "✅ Nenhuma ocorrência ou incidente registado no momento!"
            )
