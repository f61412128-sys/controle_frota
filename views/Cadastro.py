import datetime
import pandas as pd
import streamlit as st
from services.cadastros_service import (
    atualizar_motorista,
    atualizar_veiculo,
    listar_motoristas,
    listar_veiculos,
    salvar_motorista,
    salvar_veiculo,
)


def render_veiculos():
    """Tela de Gestão de Veículos."""
    st.title("🏎️ Gestão de Veículos")

    sub_tab_v_listar, sub_tab_v_novo, sub_tab_v_editar = st.tabs([
        "📋 Listar Veículos",
        "➕ Cadastrar Veículo",
        "✏️ Editar Veículo",
    ])

    # --- SUB-ABA 1: LISTAR VEÍCULOS ---
    with sub_tab_v_listar:
        st.subheader("Veículos Cadastrados")
        veiculos = listar_veiculos()
        if veiculos:
            df_v = pd.DataFrame([dict(v) for v in veiculos])
            st.dataframe(df_v, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum veículo cadastrado ainda.")

    # --- SUB-ABA 2: CADASTRAR VEÍCULO ---
    with sub_tab_v_novo:
        st.subheader("Cadastrar Novo Veículo")
        motoristas = listar_motoristas()
        opcoes_motoristas = {m["nome"]: m["id"] for m in motoristas}

        with st.form("form_veiculo", clear_on_submit=True):
            # RÁDIO DENTRO DO FORMULÁRIO
            tipo_propriedade = st.radio(
                "Propriedade do Veículo",
                ["Próprio", "Alugado"],
                horizontal=True,
                key="radio_propriedade_novo",
            )

            col1, col2, col3 = st.columns(3)
            placa = col1.text_input("Placa do Veículo*")
            marca = col2.text_input("Marca")
            modelo = col3.text_input("Modelo")

            col4, col5, col6 = st.columns(3)
            ano = col4.number_input(
                "Ano", min_value=1990, max_value=2030, value=2024
            )
            tipo = col5.selectbox(
                "Tipo",
                ["Passeio", "Utilitário", "Caminhão", "Moto", "Van"],
            )
            cor = col6.text_input("Cor")

            col7, col8 = st.columns(2)
            km_atual = col7.number_input("KM Atual", min_value=0, value=0)
            chassi = col8.text_input("Chassi")

            # CAMPOS CONDICIONAIS SE FOR ALUGADO
            locadora, inicio_contrato, fim_contrato, valor_mensal = None, None, None, 0.0
            if tipo_propriedade == "Alugado":
                st.markdown("---")
                st.markdown("##### 🏢 Dados da Locação")
                col_l1, col_l2 = st.columns(2)
                locadora = col_l1.text_input("Locadora")
                valor_mensal = col_l2.number_input(
                    "Valor Mensal (R$)", min_value=0.0, value=0.0, step=50.0
                )

                col_l3, col_l4 = st.columns(2)
                inicio_contrato = col_l3.date_input("Início do Contrato", value=datetime.date.today())
                fim_contrato = col_l4.date_input("Fim do Contrato", value=datetime.date.today())
                st.markdown("---")

            motorista_selecionado = st.selectbox(
                "Motorista Responsável",
                options=["Nenhum"] + list(opcoes_motoristas.keys()),
            )

            btn_salvar_v = st.form_submit_button("Salvar Veículo")

            if btn_salvar_v:
                if not placa:
                    st.error("Informe a placa do veículo!")
                else:
                    m_id = opcoes_motoristas.get(motorista_selecionado)
                    try:
                        salvar_veiculo(
                            placa=placa.upper(),
                            marca=marca,
                            modelo=modelo,
                            ano=ano,
                            tipo=tipo,
                            cor=cor,
                            chassi=chassi,
                            km_atual=km_atual,
                            motorista_id=m_id,
                            status="Disponível",
                            tipo_propriedade=tipo_propriedade,
                            locadora=locadora,
                            inicio_contrato=inicio_contrato,
                            fim_contrato=fim_contrato,
                            valor_mensal=valor_mensal,
                        )
                        st.success(
                            f"Veículo {placa.upper()} cadastrado com sucesso!"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")

    # --- SUB-ABA 3: EDITAR VEÍCULO ---
    with sub_tab_v_editar:
        st.subheader("Editar Dados do Veículo")
        veiculos = listar_veiculos()
        motoristas = listar_motoristas()
        opcoes_motoristas = {m["nome"]: m["id"] for m in motoristas}

        if veiculos:
            opcoes_v = {
                f"{v['placa']} - {v['modelo']} ({v['marca']})": dict(v)
                for v in veiculos
            }
            v_selecionado_str = st.selectbox(
                "Selecione o Veículo para Editar",
                list(opcoes_v.keys()),
                key="sel_v_edit",
            )
            v_dados = opcoes_v[v_selecionado_str]

            with st.form("form_editar_veiculo"):
                # RÁDIO DENTRO DO FORMULÁRIO PARA CAPTURAR CORRETAMENTE O VALOR
                prop_atual = v_dados.get("tipo_propriedade") or "Próprio"
                idx_prop = 0 if prop_atual == "Próprio" else 1
                v_tipo_propriedade = st.radio(
                    "Propriedade do Veículo",
                    ["Próprio", "Alugado"],
                    index=idx_prop,
                    horizontal=True,
                    key="radio_propriedade_edit",
                )

                col1, col2, col3 = st.columns(3)
                v_placa = col1.text_input(
                    "Placa*", value=v_dados.get("placa") or ""
                )
                v_marca = col2.text_input(
                    "Marca", value=v_dados.get("marca") or ""
                )
                v_modelo = col3.text_input(
                    "Modelo", value=v_dados.get("modelo") or ""
                )

                col4, col5, col6 = st.columns(3)
                v_ano = col4.number_input(
                    "Ano",
                    min_value=1990,
                    max_value=2030,
                    value=int(v_dados.get("ano") or 2024),
                )

                tipos_list = [
                    "Passeio",
                    "Utilitário",
                    "Caminhão",
                    "Moto",
                    "Van",
                ]
                idx_tipo = (
                    tipos_list.index(v_dados["tipo"])
                    if v_dados.get("tipo") in tipos_list
                    else 0
                )
                v_tipo = col5.selectbox("Tipo", tipos_list, index=idx_tipo)
                v_cor = col6.text_input("Cor", value=v_dados.get("cor") or "")

                col7, col8 = st.columns(2)
                v_km = col7.number_input(
                    "KM Atual",
                    min_value=0,
                    value=int(v_dados.get("km_atual") or 0),
                )
                v_chassi = col8.text_input(
                    "Chassi", value=v_dados.get("chassi") or ""
                )

                # CAMPOS CONDICIONAIS DE LOCAÇÃO DENTRO DO FORMULÁRIO
                v_locadora, v_inicio_contrato, v_fim_contrato, v_valor_mensal = None, None, None, 0.0
                if v_tipo_propriedade == "Alugado":
                    st.markdown("---")
                    st.markdown("##### 🏢 Dados da Locação")
                    col_l1, col_l2 = st.columns(2)
                    v_locadora = col_l1.text_input("Locadora", value=v_dados.get("locadora") or "")
                    v_valor_mensal = col_l2.number_input(
                        "Valor Mensal (R$)",
                        min_value=0.0,
                        value=float(v_dados.get("valor_mensal") or 0.0),
                        step=50.0,
                    )

                    dt_ini = datetime.date.today()
                    dt_fim = datetime.date.today()
                    if v_dados.get("inicio_contrato"):
                        try:
                            dt_ini = datetime.date.fromisoformat(v_dados["inicio_contrato"])
                        except Exception:
                            pass
                    if v_dados.get("fim_contrato"):
                        try:
                            dt_fim = datetime.date.fromisoformat(v_dados["fim_contrato"])
                        except Exception:
                            pass

                    col_l3, col_l4 = st.columns(2)
                    v_inicio_contrato = col_l3.date_input("Início do Contrato", value=dt_ini)
                    v_fim_contrato = col_l4.date_input("Fim do Contrato", value=dt_fim)
                    st.markdown("---")

                status_list = ["Disponível", "Em viagem", "Em manutenção", "Inativo"]
                idx_status = (
                    status_list.index(v_dados["status"])
                    if v_dados.get("status") in status_list
                    else 0
                )
                v_status = st.selectbox("Status", status_list, index=idx_status)

                m_opts = ["Nenhum"] + list(opcoes_motoristas.keys())
                m_atual = v_dados.get("motorista") or "Nenhum"
                idx_m = m_opts.index(m_atual) if m_atual in m_opts else 0
                v_motorista = st.selectbox(
                    "Motorista Responsável", options=m_opts, index=idx_m
                )

                btn_atualizar_v = st.form_submit_button("💾 Atualizar Veículo")

                if btn_atualizar_v:
                    if not v_placa:
                        st.error("O campo Placa não pode ser vazio!")
                    else:
                        try:
                            atualizar_veiculo(
                                veiculo_id=v_dados["id"],
                                placa=v_placa.upper(),
                                marca=v_marca,
                                modelo=v_modelo,
                                ano=v_ano,
                                tipo=v_tipo,
                                cor=v_cor,
                                chassi=v_chassi,
                                km_atual=v_km,
                                motorista_id=opcoes_motoristas.get(v_motorista),
                                status=v_status,
                                tipo_propriedade=v_tipo_propriedade,
                                locadora=v_locadora,
                                inicio_contrato=v_inicio_contrato,
                                fim_contrato=v_fim_contrato,
                                valor_mensal=v_valor_mensal,
                            )
                            st.success(
                                f"Veículo {v_placa.upper()} atualizado com sucesso!"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar: {e}")
        else:
            st.info("Nenhum veículo cadastrado.")


def render_motoristas():
    """Tela de Gestão de Motoristas."""
    st.title("👥 Gestão de Motoristas")

    sub_tab_m_listar, sub_tab_m_novo, sub_tab_m_editar = st.tabs([
        "📋 Listar Motoristas",
        "➕ Novo Motorista",
        "✏ Editar Motorista",
    ])

    # --- SUB-ABA 1: LISTAR MOTORISTAS ---
    with sub_tab_m_listar:
        st.subheader("Motoristas Cadastrados")
        motoristas = listar_motoristas()
        if motoristas:
            df_m = pd.DataFrame([dict(m) for m in motoristas])
            st.dataframe(df_m, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum motorista cadastrado ainda.")

    # --- SUB-ABA 2: CADASTRAR MOTORISTA ---
    with sub_tab_m_novo:
        st.subheader("Cadastrar Novo Motorista")
        with st.form("form_motorista", clear_on_submit=True):
            col1, col2 = st.columns(2)
            nome = col1.text_input("Nome Completo*")
            cpf = col2.text_input("CPF / Matrícula*")

            col3, col4, col5 = st.columns(3)
            telefone = col3.text_input("Telefone")
            cnh = col4.text_input("Nº CNH")
            categoria = col5.selectbox(
                "Categoria CNH",
                ["A", "B", "C", "D", "E", "AB", "AC", "AD", "AE"],
            )
            validade_cnh = st.date_input("Validade CNH")

            btn_salvar_m = st.form_submit_button("Guardar Motorista")

            if btn_salvar_m:
                if not nome or not cpf:
                    st.error("Preencha os campos obrigatórios (Nome e CPF)!")
                else:
                    try:
                        salvar_motorista(
                            nome,
                            cpf,
                            telefone,
                            cnh,
                            categoria,
                            validade_cnh,
                        )
                        st.success(f"Motorista {nome} cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")

    # --- SUB-ABA 3: EDITAR MOTORISTA ---
    with sub_tab_m_editar:
        st.subheader("Editar Dados do Motorista")
        motoristas = listar_motoristas()
        if motoristas:
            opcoes_m = {
                f"{m['nome']} (CPF: {m['cpf_matricula']})": dict(m)
                for m in motoristas
            }
            m_selecionado_str = st.selectbox(
                "Selecione o Motorista para Editar",
                list(opcoes_m.keys()),
                key="sel_m_edit",
            )
            m_dados = opcoes_m[m_selecionado_str]

            with st.form("form_editar_motorista"):
                col1, col2 = st.columns(2)
                m_nome = col1.text_input(
                    "Nome Completo*", value=m_dados["nome"]
                )
                m_cpf = col2.text_input(
                    "CPF / Matrícula*", value=m_dados["cpf_matricula"]
                )

                col3, col4, col5 = st.columns(3)
                m_telefone = col3.text_input(
                    "Telefone", value=m_dados.get("telefone") or ""
                )
                m_cnh = col4.text_input("Nº CNH", value=m_dados.get("cnh") or "")

                cats = ["A", "B", "C", "D", "E", "AB", "AC", "AD", "AE"]
                idx_cat = (
                    cats.index(m_dados["categoria_cnh"])
                    if m_dados.get("categoria_cnh") in cats
                    else 1
                )
                m_categoria = col5.selectbox("Categoria CNH", cats, index=idx_cat)

                dt_val_cnh = datetime.date.today()
                if m_dados.get("validade_cnh"):
                    try:
                        dt_val_cnh = datetime.date.fromisoformat(m_dados["validade_cnh"])
                    except Exception:
                        pass
                m_validade_cnh = st.date_input("Validade CNH", value=dt_val_cnh)

                m_status_opcoes = ["Ativo", "Inativo"]
                idx_status = (
                    m_status_opcoes.index(m_dados["status"])
                    if m_dados.get("status") in m_status_opcoes
                    else 0
                )
                m_status = st.selectbox(
                    "Status", m_status_opcoes, index=idx_status
                )

                btn_atualizar_m = st.form_submit_button("💾 Atualizar Motorista")

                if btn_atualizar_m:
                    if not m_nome or not m_cpf:
                        st.error("Nome e CPF são obrigatórios!")
                    else:
                        try:
                            atualizar_motorista(
                                m_dados["id"],
                                m_nome,
                                m_cpf,
                                m_telefone,
                                m_cnh,
                                m_categoria,
                                m_validade_cnh,
                                m_status,
                            )
                            st.success(
                                f"Motorista {m_nome} atualizado com sucesso!"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar: {e}")
        else:
            st.info("Nenhum motorista cadastrado.")
