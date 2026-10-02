import datetime
import pandas as pd
import streamlit as st
from database.connection import get_connection


def render_cards_veiculos_estilizados(df_veiculos):
    if df_veiculos.empty:
        st.info("Nenhum veículo registado nesta secção.")
        return

    st.markdown("""
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
    """, unsafe_allow_html=True)

    for _, row in df_veiculos.iterrows():
        placa = str(row.get('placa', 'N/A'))
        modelo = str(row.get('modelo', 'N/A'))
        tipo = str(row.get('tipo_propriedade', row.get('tipo', 'N/A')))
        
        status_disp = row.get('status_disponibilidade', 'Disponível')
        ultimo_resp = row.get('ultimo_responsavel', 'Sem registo')
        tipo_mov = row.get('ultimo_tipo_movimento', '')
        
        if status_disp == 'Disponível':
            badge_html = '<span class="badge-disponivel">🟢 Disponível (No Pátio)</span>'
        else:
            badge_html = '<span class="badge-indisponivel">🔴 Em Uso / Indisponível</span>'

        mov_text = f" ({tipo_mov})" if tipo_mov else ""

        st.markdown(f"""
            <div class="veiculo-card">
                <div class="veiculo-header">
                    <span class="veiculo-placa">🚗 {placa}</span>
                    {badge_html}
                </div>
                <div class="veiculo-info">Modelo: <span>{modelo}</span></div>
                <div class="veiculo-info">Tipo: <span>{tipo}</span></div>
                <div class="veiculo-info">Último Registo{mov_text}: <span>{ultimo_resp}</span></div>
            </div>
        """, unsafe_allow_html=True)


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

    df_tables = ler_tabela_direta("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tabelas_existentes = df_tables['table_name'].tolist() if not df_tables.empty else []

    df_veiculos = ler_tabela_direta("SELECT * FROM veiculos") if 'veiculos' in tabelas_existentes else pd.DataFrame()
    df_manutencoes = ler_tabela_direta("SELECT * FROM manutencoes") if 'manutencoes' in tabelas_existentes else pd.DataFrame()
    df_motoristas = ler_tabela_direta("SELECT * FROM motoristas") if 'motoristas' in tabelas_existentes else pd.DataFrame()
    df_usuarios = ler_tabela_direta("SELECT * FROM usuarios") if 'usuarios' in tabelas_existentes else pd.DataFrame()

    df_checklists = pd.DataFrame()
    
    for t in ['checklists', 'checklist', 'historico_checklists', 'inspecoes']:
        if t in tabelas_existentes:
            df_temp = ler_tabela_direta(f"SELECT * FROM {t}")
            if not df_temp.empty:
                df_checklists = df_temp
                break

    if df_checklists.empty:
        for t in tabelas_existentes:
            df_temp = ler_tabela_direta(f"SELECT * FROM {t}")
            if not df_temp.empty and any(k in t.lower() for k in ['check', 'insp', 'vist']):
                df_checklists = df_temp
                break

    # Cruzamento inteligente de checklists (Entrada/Saída e Responsável/Admin)
    if not df_veiculos.empty:
        status_list = []
        resp_list = []
        tipo_mov_list = []

        for _, v_row in df_veiculos.iterrows():
            v_id = v_row.get('id')
            
            df_chk_veiculo = pd.DataFrame()
            if not df_checklists.empty and 'veiculo_id' in df_checklists.columns and v_id is not None:
                mask = df_checklists['veiculo_id'] == v_id
                df_chk_veiculo = df_checklists[mask]

            if not df_chk_veiculo.empty:
                col_data = None
                for c in ['data_hora', 'created_at', 'data', 'data_checklist', 'timestamp']:
                    if c in df_chk_veiculo.columns:
                        col_data = c
                        break
                
                if col_data:
                    try:
                        df_chk_veiculo = df_chk_veiculo.sort_values(by=col_data, ascending=False)
                    except Exception:
                        pass

                ult_chk = df_chk_veiculo.iloc[0]

                # Tenta descobrir o responsável
                resp = "Administrador / Sistema"
                for col_resp in ['responsavel', 'usuario_responsavel', 'nome_responsavel']:
                    if col_resp in ult_chk and pd.notna(ult_chk[col_resp]):
                        resp = str(ult_chk[col_resp])
                        break
                
                if resp == "Administrador / Sistema" or resp.isdigit():
                    for id_col in ['usuario_id', 'admin_id', 'criado_por_id']:
                        if id_col in ult_chk and pd.notna(ult_chk[id_col]) and not df_usuarios.empty and 'id' in df_usuarios.columns:
                            u_match = df_usuarios[df_usuarios['id'] == ult_chk[id_col]]
                            if not u_match.empty:
                                resp = str(u_match.iloc[0].get('nome', u_match.iloc[0].get('usuario', 'Admin')))
                                break

                if resp == "Administrador / Sistema" or resp.isdigit():
                    motorista_id = ult_chk.get('motorista_id')
                    if motorista_id is not None and not df_motoristas.empty and 'id' in df_motoristas.columns:
                        m_match = df_motoristas[df_motoristas['id'] == motorista_id]
                        if not m_match.empty:
                            resp = str(m_match.iloc[0].get('nome', 'Motorista'))

                # Detetar se é Saída ou Entrada
                tipo_mov = ""
                for col_tipo in ['tipo_operacao', 'tipo_movimento', 'operacao', 'movimento', 'fluxo']:
                    if col_tipo in ult_chk and pd.notna(ult_chk[col_tipo]):
                        tipo_mov = str(ult_chk[col_tipo])
                        break

                tipo_mov_lower = tipo_mov.lower()
                if any(k in tipo_mov_lower for k in ['saida', 'retirada', 'saída', 'uso']):
                    status_disp = "Indisponível"
                elif any(k in tipo_mov_lower for k in ['entrada', 'devolucao', 'devolução', 'retorno', 'chegada']):
                    status_disp = "Disponível"
                else:
                    status_disp = "Disponível"

                status_list.append(status_disp)
                resp_list.append(resp)
                tipo_mov_list.append(tipo_mov if tipo_mov else "Registo Geral")
            else:
                status_list.append("Disponível")
                resp_list.append("Sem checklist recente")
                tipo_mov_list.append("")

        df_veiculos['status_disponibilidade'] = status_list
        df_veiculos['ultimo_responsavel'] = resp_list
        df_veiculos['ultimo_tipo_movimento'] = tipo_mov_list
    else:
        df_veiculos['status_disponibilidade'] = "Disponível"
        df_veiculos['ultimo_responsavel'] = "N/A"
        df_veiculos['ultimo_tipo_movimento'] = ""

    # Cálculo do Custo de Manutenções
    custo_total_manut = 0.0
    if not df_manutencoes.empty:
        for col_val in ['valor', 'custo', 'preco', 'valor_total']:
            if col_val in df_manutencoes.columns:
                try:
                    valores_limpos = pd.to_numeric(
                        df_manutencoes[col_val].astype(str)
                        .str.replace('R$', '', regex=True)
                        .str.replace('.', '', regex=False)
                        .str.replace(',', '.', regex=False),
                        errors='coerce'
                    )
                    custo_total_manut = float(valores_limpos.sum())
                    break
                except Exception:
                    pass

    # Cálculo dinâmico de Contratos a Vencer / Vencidos
    total_venc_contratos = 0
    df_contratos = pd.DataFrame()
    for t_c in ['contratos', 'locacoes', 'gestao_contratos']:
        if t_c in tabelas_existentes:
            df_temp = ler_tabela_direta(f"SELECT * FROM {t_c}")
            if not df_temp.empty:
                df_contratos = df_temp
                break

    if not df_contratos.empty:
        col_venc = None
        for c in ['data_fim', 'vencimento', 'termino_contrato', 'data_termino', 'vencimento_contrato']:
            if c in df_contratos.columns:
                col_venc = c
                break
        if col_venc:
            try:
                hoje = pd.Timestamp.now().normalize()
                datas_venc = pd.to_datetime(df_contratos[col_venc], errors='coerce')
                limite = hoje + pd.Timedelta(days=30)
                total_venc_contratos = int(((datas_venc >= hoje) & (datas_venc <= limite)).sum() + (datas_venc < hoje).sum())
            except Exception:
                pass
    elif not df_veiculos.empty:
        col_venc_v = None
        for c in ['vencimento_contrato', 'data_fim_contrato', 'fim_contrato', 'vencimento']:
            if c in df_veiculos.columns:
                col_venc_v = c
                break
        if col_venc_v:
            try:
                hoje = pd.Timestamp.now().normalize()
                datas_venc = pd.to_datetime(df_veiculos[col_venc_v], errors='coerce')
                limite = hoje + pd.Timedelta(days=30)
                total_venc_contratos = int(((datas_venc >= hoje) & (datas_venc <= limite)).sum() + (datas_venc < hoje).sum())
            except Exception:
                pass

    df_alugados = pd.DataFrame()
    df_proprios = pd.DataFrame()

    if not df_veiculos.empty:
        col_alvo = None
        for c in ['tipo_propriedade', 'tipo', 'posse', 'categoria']:
            if c in df_veiculos.columns:
                col_alvo = c
                break

        if col_alvo:
            mask_alug = df_veiculos[col_alvo].astype(str).str.lower().str.contains("alugado|terceirizado|locado|terceiro", na=False)
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

    tab_contratos, tab_rodizio, tab_manut, tab_pendencias = st.tabs([
        "📄 Gestão de Contratos & Frota",
        "🚘 Rodízio Hoje",
        "🛠 Manutenções Recentes",
        "⚠ Ocorrências",
    ])

    with tab_contratos:
        sub_alug, sub_prop = st.tabs(["📋 Alugados / Terceirizados", "🏢 Próprios"])
        with sub_alug:
            render_cards_veiculos_estilizados(df_alugados)
        with sub_prop:
            render_cards_veiculos_estilizados(df_proprios)

    with tab_rodizio:
        st.markdown("##### Consulta de Rodízio (SP)")
        hoje_idx = datetime.datetime.now().weekday()
        regras = {0: "Placas 1 e 2", 1: "Placas 3 e 4", 2: "Placas 5 e 6", 3: "Placas 7 e 8", 4: "Placas 9 e 0"}
        if hoje_idx < 5:
            st.warning(f"🚫 Restrição hoje: {regras.get(hoje_idx)}")
        else:
            st.success("✅ Sem restrição no fim de semana.")

    with tab_manut:
        if not df_manutencoes.empty:
            st.dataframe(df_manutencoes, use_container_width=True, hide_index=True)
        else:
            st.info("Sem manutenções recentes registadas.")

    with tab_pendencias:
        st.success("Nenhuma ocorrência pendente!")
