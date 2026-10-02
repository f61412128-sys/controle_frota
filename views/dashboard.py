import datetime
import pandas as pd
import streamlit as st
from database.connection import get_connection


def render_cards_veiculos_estilizados(df_veiculos):
    if df_veiculos.empty:
        st.info("Nenhum veículo registado nesta secção.")
        return

    # Estilo CSS atualizado com as tags de Disponível / Indisponível e indicador visual
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
        
        # Dados do último checklist vindos do cruzamento
        status_disp = row.get('status_disponibilidade', 'Indisponível')
        ultimo_resp = row.get('ultimo_responsavel', 'Nenhum registo')
        
        if status_disp == 'Disponível':
            badge_html = '<span class="badge-disponivel">🟢 Disponível</span>'
        else:
            badge_html = '<span class="badge-indisponivel">🔴 Indisponível</span>'

        st.markdown(f"""
            <div class="veiculo-card">
                <div class="veiculo-header">
                    <span class="veiculo-placa">🚗 {placa}</span>
                    {badge_html}
                </div>
                <div class="veiculo-info">Modelo: <span>{modelo}</span></div>
                <div class="veiculo-info">Tipo: <span>{tipo}</span></div>
                <div class="veiculo-info">Último Checklist por: <span>{ultimo_resp}</span></div>
            </div>
        """, unsafe_allow_html=True)


def render_dashboard(contar_registros_fn=None):
    st.title("📊 Painel Geral")

    conn = get_connection()
    try:
        df_veiculos = pd.read_sql_query("SELECT * FROM veiculos", conn)
    except Exception:
        df_veiculos = pd.DataFrame()

    try:
        df_manutencoes = pd.read_sql_query("SELECT * FROM manutencoes", conn)
    except Exception:
        df_manutencoes = pd.DataFrame()

    try:
        df_motoristas = pd.read_sql_query("SELECT * FROM motoristas", conn)
    except Exception:
        df_motoristas = pd.DataFrame()

    try:
        df_checklists = pd.read_sql_query("SELECT * FROM checklists", conn)
    except Exception:
        df_checklists = pd.DataFrame()

    # Carregar contratos
    df_contratos = pd.DataFrame()
    try:
        df_contratos = pd.read_sql_query("SELECT * FROM contratos", conn)
    except Exception:
        try:
            df_contratos = pd.read_sql_query("SELECT * FROM vencimento_contratos", conn)
        except Exception:
            pass

    conn.close()

    # Cruzamento inteligente com a tabela de checklists para cada veículo
    if not df_veiculos.empty:
        status_list = []
        resp_list = []

        for _, v_row in df_veiculos.iterrows():
            # Tentar identificar a placa do veículo em várias colunas possíveis
            p_val = str(v_row.get('placa', '')).strip()
            id_val = str(v_row.get('id', ''))

            df_chk_veiculo = pd.DataFrame()
            if not df_checklists.empty:
                # Procurar colunas comuns de referência ao veículo no checklist
                col_chk_veiculo = None
                for c in ['placa', 'veiculo_placa', 'veiculo_id', 'id_veiculo', 'veiculo']:
                    if c in df_checklists.columns:
                        col_chk_veiculo = c
                        break
                
                if col_chk_veiculo:
                    mask = df_checklists[col_chk_veiculo].astype(str).str.strip().str.upper() == p_val.upper()
                    df_chk_veiculo = df_checklists[mask]

            if not df_chk_veiculo.empty:
                # Ordenar por data se existir coluna de data ou ID decrescente para pegar o mais recente
                col_data = None
                for c in ['data', 'data_checklist', 'created_at', 'data_hora', 'id']:
                    if c in df_chk_veiculo.columns:
                        col_data = c
                        break
                
                if col_data:
                    try:
                        df_chk_veiculo = df_chk_veiculo.sort_values(by=col_data, ascending=False)
                    except Exception:
                        pass

                ult_chk = df_chk_veiculo.iloc[0]

                # Descobrir quem fez o checklist (procurando colunas de utilizador, responsavel, motorista, admin)
                resp = "Desconhecido"
                for c_resp in ['usuario', 'responsavel', 'motorista', 'nome', 'criado_por', 'adm']:
                    if c_resp in ult_chk and pd.notna(ult_chk[c_resp]):
                        resp = str(ult_chk[c_resp])
                        break

                resp_lower = resp.lower()
                # Regra: Se foi feito pelo adm (ou contem admin/administrador) e sem pendências graves, fica Disponível
                # Caso contrário (outro utilizador/motorista), fica Indisponível para validação
                is_adm = "adm" in resp_lower or "administrador" in resp_lower
                
                # Verificar se há status explícito de aprovação
                status_aprovado = True
                for c_status in ['status', 'aprovado', 'situacao']:
                    if c_status in ult_chk and pd.notna(ult_chk[c_status]):
                        val_st = str(ult_chk[c_status]).lower()
                        if any(neg in val_st for n in ['reprov', 'pend', 'manuten', 'nao', 'false']):
                            status_aprovado = False

                if is_adm and status_aprovado:
                    status_list.append("Disponível")
                else:
                    status_list.append("Indisponível")
                
                resp_list.append(resp)
            else:
                status_list.append("Indisponível")
                resp_list.append("Sem checklist recente")

        df_veiculos['status_disponibilidade'] = status_list
        df_veiculos['ultimo_responsavel'] = resp_list
    else:
        df_veiculos['status_disponibilidade'] = "Indisponível"
        df_veiculos['ultimo_responsavel'] = "N/A"

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

    # Verificação de contratos
    total_contratos_venc = len(df_contratos)
    if not df_contratos.empty:
        for col_dt in ['vencimento', 'data_fim', 'fim_contrato', 'data_vencimento']:
            if col_dt in df_contratos.columns:
                try:
                    dt_venc = pd.to_datetime(df_contratos[col_dt], errors='coerce')
                    hoje = pd.Timestamp.today()
                    proximos = df_contratos[(dt_venc >= hoje) & (dt_venc <= hoje + pd.Timedelta(days=30))]
                    total_contratos_venc = len(proximos)
                    break
                except Exception:
                    pass

    # Separação correta de veículos
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
            
            mask_prop = df_veiculos[col_alvo].astype(str).str.lower().str.contains("próprio|proprio", na=False)
            df_proprios = df_veiculos[mask_prop].copy()
            
            if df_proprios.empty:
                df_proprios = df_veiculos[~mask_alug].copy()
        else:
            df_proprios = df_veiculos.copy()

    total_veiculos = len(df_veiculos)
    total_proprios = len(df_proprios)
    total_alugados = len(df_alugados)
    total_motoristas = len(df_motoristas) if not df_motoristas.empty else 0
    total_manut = len(df_manutencoes)

    # Métricas Superiores
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚚 Frota Total", total_veiculos)
    c2.metric("🏢 Próprios", total_proprios)
    c3.metric("📋 Alugados", total_alugados)
    c4.metric("🛠 Em Manutenção", total_manut)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("💰 Custo Manutenções", f"R$ {custo_total_manut:,.2f}")
    c6.metric("👨‍✈️ Motoristas", total_motoristas)
    c7.metric("⚠ Ocorrências", 0)
    
    delta_contrato = "Atenção" if total_contratos_venc > 0 else "OK"
    c8.metric("📄 Venc. Contratos", total_contratos_venc, delta=delta_contrato, delta_color="inverse" if total_contratos_venc > 0 else "normal")

    st.divider()

    # Abas Principais
    tab_contratos, tab_rodizio, tab_manut, tab_pendencias = st.tabs([
        "📄 Gestão de Contratos & Frota",
        "🚘 Rodízio Hoje",
        "🛠 Manutenções Recentes",
        "⚠ Ocorrências",
    ])

    with tab_contratos:
        sub_alug, sub_prop = st.tabs(["📋 Alugados / Terceirizados", "🏢 Próprios"])

        with sub_alug:
            st.markdown("##### Veículos Alugados / Terceirizados")
            render_cards_veiculos_estilizados(df_alugados)

        with sub_prop:
            st.markdown("##### Veículos Próprios")
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
