import base64
import datetime
import os
from pathlib import Path
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st
from config import DB_PATH
from database.models import contar_registros, init_db
from views.Checklist import render as render_checklist
from views.dashboard import render_dashboard
from views.Manutenções import render as render_manutencoes
from views.services.cadastros_service import (
    atualizar_motorista,
    atualizar_veiculo,
    autenticar_usuario,
    listar_motoristas,
    listar_usuarios,
    listar_veiculos,
    salvar_motorista,
    salvar_usuario,
    salvar_veiculo,
)

# Configuração da página
st.set_page_config(
    page_title="Controle de Frota",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Estilização CSS geral e limpeza de layout
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    body {
        overscroll-behavior-y: none;
    }
    
    .block-container {
        padding-top: 0.4rem;
        padding-bottom: 2rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }
    
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 2.8em;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Inicialização do Banco
try:
    init_db()
except Exception as e:
    st.error("Erro ao inicializar o banco de dados:")
    st.exception(e)
    st.stop()

# --- GESTÃO DE SESSÃO COM URL BLINDADA (ANTI-REFRESH) ---
params = st.query_params

if "logado" not in st.session_state:
    if params.get("logado") == "true":
        st.session_state["logado"] = True
        st.session_state["perfil"] = params.get("perfil", "admin")
        st.session_state["usuario_nome"] = params.get("nome", "Administrador")
        mot_id_str = params.get("motorista_id")
        st.session_state["motorista_id"] = (
            int(mot_id_str) if mot_id_str and mot_id_str.isdigit() else None
        )
    else:
        st.session_state["logado"] = False
        st.session_state["perfil"] = None
        st.session_state["usuario_nome"] = ""
        st.session_state["motorista_id"] = None

if not st.session_state["logado"]:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🚚 Controle de Frota")
        st.subheader("Acesso ao Sistema")

        usuario_input = st.text_input("Usuário")
        senha_input = st.text_input("Senha", type="password")
        btn_entrar = st.button("Entrar", use_container_width=True)

        if btn_entrar:
            usuario_db = autenticar_usuario(usuario_input, senha_input)

            if usuario_db or (
                usuario_input.lower() == "admin" and senha_input == "admin123"
            ):
                if usuario_db:
                    perfil = usuario_db["perfil"]
                    nome = usuario_db["login"].capitalize()
                    mot_id = usuario_db["motorista_id"]
                else:
                    perfil = "admin"
                    nome = "Administrador Mestre"
                    mot_id = ""

                st.session_state["logado"] = True
                st.session_state["perfil"] = perfil
                st.session_state["usuario_nome"] = nome
                st.session_state["motorista_id"] = mot_id

                st.query_params["logado"] = "true"
                st.query_params["perfil"] = perfil
                st.query_params["nome"] = nome
                if mot_id:
                    st.query_params["motorista_id"] = str(mot_id)

                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

else:
    # --- CABEÇALHO SUPERIOR FIXO PARA O TELEMÓVEL (MENU + LOGOUT) ---
    c_topo1, c_topo2 = st.columns([3, 1])
    with c_topo1:
        st.caption(
            f"👤 **{st.session_state['usuario_nome']}** "
            f"({str(st.session_state['perfil']).upper()})"
        )
    with c_topo2:
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["logado"] = False
            st.session_state["perfil"] = None
            st.session_state["usuario_nome"] = ""
            st.session_state["motorista_id"] = None
            st.query_params.clear()
            st.rerun()

    st.divider()

    # --- PERFIL MOTORISTA ---
    if st.session_state["perfil"] == "motorista":
        st.info("📱 Modo Checklist Ativo")
        render_checklist()

    # --- PERFIL ADMINISTRADOR ---
    elif st.session_state["perfil"] == "admin":
        opcoes_menu = [
            "Dashboard",
            "Gestão de Usuários",
            "Veículos",
            "Motoristas",
            "Checklist",
            "Manutenções",
        ]

        opcao = st.selectbox(
            "📍 Selecione o Módulo do Sistema:",
            opcoes_menu,
            label_visibility="collapsed",
        )
        st.markdown("---")

        if opcao == "Dashboard":
            render_dashboard(contar_registros)

        elif opcao == "Gestão de Usuários":
            st.title("🔒 Gestão de Usuários e Acessos")
            tab_listar, tab_cadastrar, tab_editar = st.tabs([
                "📋 Usuários Cadastrados",
                "➕ Criar Novo Login",
                "✏ Editar / Vincular Usuário",
            ])

            usuarios = listar_usuarios()
            motoristas = listar_motoristas()
            opcoes_m = {m["nome"]: m["id"] for m in motoristas}

            with tab_listar:
                if usuarios:
                    st.dataframe(
                        pd.DataFrame([dict(u) for u in usuarios]),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Nenhum usuário cadastrado.")

            with tab_cadastrar:
                with st.form("form_cadastrar_usuario", clear_on_submit=True):
                    nome_completo = st.text_input(
                        "Nome Completo do Funcionário*"
                    )
                    c1, c2 = st.columns(2)
                    login_novo = c1.text_input("Nome de Usuário (Login)*")
                    senha_nova = c2.text_input("Senha*", type="password")

                    c3, c4 = st.columns(2)
                    perfil_novo = c3.selectbox(
                        "Perfil de Acesso*", ["motorista", "admin"]
                    )
                    motorista_vinc = c4.selectbox(
                        "Vincular ao Motorista (Opcional)",
                        options=["Nenhum"] + list(opcoes_m.keys()),
                    )

                    if st.form_submit_button("Criar Usuário"):
                        if nome_completo and login_novo and senha_nova:
                            salvar_usuario(
                                nome_completo,
                                login_novo,
                                senha_nova,
                                perfil_novo,
                            )
                            st.success("Usuário criado com sucesso!")
                            st.rerun()

            with tab_editar:
                if usuarios:
                    mapa_u = {
                        f"{u['login']} ({u['nome']})": dict(u)
                        for u in usuarios
                    }
                    u_dados = mapa_u[
                        st.selectbox(
                            "Selecione o Usuário", list(mapa_u.keys())
                        )
                    ]

                    with st.form("form_editar_usuario"):
                        novo_nome = st.text_input(
                            "Nome Completo", value=u_dados.get("nome", "")
                        )
                        novo_perfil = st.selectbox(
                            "Perfil de Acesso",
                            ["motorista", "admin"],
                            index=0
                            if u_dados.get("perfil") == "motorista"
                            else 1,
                        )
                        m_opts = ["Nenhum"] + list(opcoes_m.keys())
                        m_atual = u_dados.get("motorista_nome") or "Nenhum"
                        idx_m = m_opts.index(m_atual) if m_atual in m_opts else 0
                        novo_m_vinc = st.selectbox(
                            "Motorista Vinculado", options=m_opts, index=idx_m
                        )

                        if st.form_submit_button("Salvar Alterações"):
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE usuarios SET nome = ?, perfil = ?, motorista_id = ? WHERE id = ?",
                                (
                                    novo_nome,
                                    novo_perfil,
                                    opcoes_m.get(novo_m_vinc),
                                    u_dados["id"],
                                ),
                            )
                            conn.commit()
                            conn.close()
                            st.success("Usuário atualizado!")
                            st.rerun()

        # --- TELA: VEÍCULOS ---
        elif opcao == "Veículos":
            st.title("🚘 Gestão de Veículos")
            tab_listar, tab_cadastrar, tab_editar = st.tabs([
                "📋 Listar Veículos",
                "➕ Cadastrar Veículo",
                "✏ Editar Veículo",
            ])

            veiculos = listar_veiculos()
            motoristas = listar_motoristas()
            opcoes_motoristas = {m["nome"]: m["id"] for m in motoristas}

            with tab_listar:
                if veiculos:
                    st.dataframe(
                        pd.DataFrame([dict(v) for v in veiculos]),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Nenhum veículo cadastrado.")

            with tab_cadastrar:
                with st.form("form_cadastrar_veiculo", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)
                    placa = c1.text_input("Placa do Veículo*").upper().strip()
                    marca = c2.text_input("Marca")
                    modelo = c3.text_input("Modelo")

                    c4, c5, c6 = st.columns(3)
                    ano = c4.number_input(
                        "Ano", min_value=1990, max_value=2030, value=2024
                    )
                    tipo = c5.selectbox(
                        "Tipo",
                        ["Passeio", "Utilitário", "Caminhão", "Moto", "Van"],
                    )
                    cor = c6.text_input("Cor")

                    c7, c8 = st.columns(2)
                    km_atual = c7.number_input("KM Atual", min_value=0, value=0)
                    chassi = c8.text_input("Chassi")

                    st.subheader("Informações de Propriedade")
                    c9, c10 = st.columns(2)
                    tipo_propriedade = c9.selectbox(
                        "Tipo de Propriedade*",
                        ["Próprio", "Alugado", "Terceirizado"],
                    )
                    locadora = c10.text_input("Locadora (se alugado)")

                    c11, c12, c13 = st.columns(3)
                    inicio_contrato = c11.date_input(
                        "Início do Contrato", value=datetime.date.today()
                    )
                    fim_contrato = c12.date_input(
                        "Fim do Contrato", value=datetime.date.today()
                    )
                    valor_mensal = c13.number_input(
                        "Valor Mensal (R$)",
                        min_value=0.0,
                        value=0.0,
                        step=100.0,
                    )

                    motorista_sel = st.selectbox(
                        "Motorista Responsável",
                        options=["Nenhum"] + list(opcoes_motoristas.keys()),
                    )

                    if st.form_submit_button("Salvar Veículo"):
                        if placa:
                            salvar_veiculo(
                                placa=placa,
                                marca=marca,
                                modelo=modelo,
                                ano=ano,
                                tipo=tipo,
                                cor=cor,
                                chassi=chassi,
                                km_atual=km_atual,
                                motorista_id=opcoes_motoristas.get(
                                    motorista_sel
                                ),
                                tipo_propriedade=tipo_propriedade,
                                locadora=locadora
                                if tipo_propriedade != "Próprio"
                                else None,
                                inicio_contrato=inicio_contrato
                                if tipo_propriedade != "Próprio"
                                else None,
                                fim_contrato=fim_contrato
                                if tipo_propriedade != "Próprio"
                                else None,
                                valor_mensal=valor_mensal
                                if tipo_propriedade != "Próprio"
                                else 0.0,
                                status="Disponível",
                            )
                            st.success("Veículo cadastrado com sucesso!")
                            st.rerun()

            with tab_editar:
                if veiculos:
                    mapa_v = {
                        f"{v['placa']} - {v['modelo']}": dict(v)
                        for v in veiculos
                    }
                    v_selecionado = st.selectbox(
                        "Selecione o Veículo para Editar",
                        list(mapa_v.keys()),
                        key="select_edit_veiculo",
                    )
                    v_dados = mapa_v[v_selecionado]

                    with st.form("form_editar_veiculo"):
                        c1, c2, c3 = st.columns(3)
                        e_placa = c1.text_input("Placa", value=v_dados["placa"])
                        e_marca = c2.text_input("Marca", value=v_dados["marca"])
                        e_modelo = c3.text_input(
                            "Modelo", value=v_dados["modelo"]
                        )

                        c4, c5, c6 = st.columns(3)
                        e_ano = c4.number_input(
                            "Ano",
                            min_value=1990,
                            max_value=2030,
                            value=int(v_dados["ano"] or 2024),
                        )
                        tipos_list = [
                            "Passeio",
                            "Utilitário",
                            "Caminhão",
                            "Moto",
                            "Van",
                        ]
                        tipo_atual_db = v_dados.get("tipo", "Passeio")
                        idx_tipo = (
                            tipos_list.index(tipo_atual_db)
                            if tipo_atual_db in tipos_list
                            else 0
                        )
                        e_tipo = c5.selectbox(
                            "Tipo", tipos_list, index=idx_tipo
                        )
                        e_cor = c6.text_input(
                            "Cor", value=v_dados.get("cor", "")
                        )

                        c7, c8 = st.columns(2)
                        e_km = c7.number_input(
                            "KM Atual",
                            min_value=0,
                            value=int(v_dados.get("km_atual") or 0),
                        )
                        e_chassi = c8.text_input(
                            "Chassi", value=v_dados.get("chassi", "")
                        )

                        st.subheader("Informações de Propriedade")
                        c9, c10 = st.columns(2)
                        props_list = ["Próprio", "Alugado", "Terceirizado"]
                        prop_atual = v_dados.get("tipo_propriedade") or "Próprio"
                        idx_p = (
                            props_list.index(prop_atual)
                            if prop_atual in props_list
                            else 0
                        )
                        e_tipo_propriedade = c9.selectbox(
                            "Tipo de Propriedade", props_list, index=idx_p
                        )
                        e_locadora = c10.text_input(
                            "Locadora", value=v_dados.get("locadora") or ""
                        )

                        c11, c12, c13 = st.columns(3)

                        def parse_data(val):
                            if not val:
                                return datetime.date.today()
                            try:
                                return datetime.datetime.strptime(
                                    str(val).split()[0], "%Y-%m-%d"
                                ).date()
                            except Exception:
                                return datetime.date.today()

                        e_inicio_contrato = c11.date_input(
                            "Início do Contrato",
                            value=parse_data(v_dados.get("inicio_contrato")),
                        )
                        e_fim_contrato = c12.date_input(
                            "Fim do Contrato",
                            value=parse_data(v_dados.get("fim_contrato")),
                        )
                        e_valor_mensal = c13.number_input(
                            "Valor Mensal (R$)",
                            min_value=0.0,
                            value=float(v_dados.get("valor_mensal") or 0.0),
                            step=100.0,
                        )

                        m_opts = ["Nenhum"] + list(opcoes_motoristas.keys())
                        m_atual = v_dados.get("motorista") or "Nenhum"
                        idx_m = m_opts.index(m_atual) if m_atual in m_opts else 0
                        e_motorista = st.selectbox(
                            "Motorista Responsável", options=m_opts, index=idx_m
                        )

                        if st.form_submit_button("Atualizar Veículo"):
                            atualizar_veiculo(
                                veiculo_id=v_dados["id"],
                                placa=e_placa,
                                marca=e_marca,
                                modelo=e_modelo,
                                ano=e_ano,
                                tipo=e_tipo,
                                cor=e_cor,
                                chassi=e_chassi,
                                km_atual=e_km,
                                motorista_id=opcoes_motoristas.get(e_motorista),
                                tipo_propriedade=e_tipo_propriedade,
                                locadora=e_locadora
                                if e_tipo_propriedade != "Próprio"
                                else None,
                                inicio_contrato=e_inicio_contrato
                                if e_tipo_propriedade != "Próprio"
                                else None,
                                fim_contrato=e_fim_contrato
                                if e_tipo_propriedade != "Próprio"
                                else None,
                                valor_mensal=e_valor_mensal
                                if e_tipo_propriedade != "Próprio"
                                else 0.0,
                                status=v_dados.get("status", "Disponível"),
                            )
                            st.success("Veículo atualizado com sucesso!")
                            st.rerun()

        # --- TELA: MOTORISTAS ---
        elif opcao == "Motoristas":
            st.title("👨‍✈ Gestão de Motoristas")
            tab_listar, tab_cadastrar, tab_editar = st.tabs([
                "📋 Listar Motoristas",
                "➕ Cadastrar Motorista",
                "✏ Editar Motorista",
            ])

            motoristas = listar_motoristas()

            with tab_listar:
                if motoristas:
                    st.dataframe(
                        pd.DataFrame([dict(m) for m in motoristas]),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Nenhum motorista cadastrado.")

            with tab_cadastrar:
                with st.form("form_cadastrar_motorista", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    nome = c1.text_input("Nome Completo*")
                    cpf = c2.text_input("CPF / Matrícula*")

                    c3, c4, c5 = st.columns(3)
                    telefone = c3.text_input("Telefone")
                    cnh = c4.text_input("Número CNH")
                    categoria = c5.selectbox(
                        "Categoria CNH",
                        ["A", "B", "C", "D", "E", "AB", "AC", "AD", "AE"],
                    )
                    validade = st.date_input("Validade CNH")

                    if st.form_submit_button("Salvar Motorista"):
                        if nome and cpf:
                            salvar_motorista(
                                nome, cpf, telefone, cnh, categoria, validade
                            )
                            st.success("Motorista cadastrado!")
                            st.rerun()

            with tab_editar:
                if motoristas:
                    mapa_m = {
                        f"{m['nome']} ({m['cpf_matricula']})": dict(m)
                        for m in motoristas
                    }
                    m_dados = mapa_m[
                        st.selectbox(
                            "Selecione o Motorista para Editar",
                            list(mapa_m.keys()),
                        )
                    ]

                    with st.form("form_editar_motorista"):
                        c1, c2 = st.columns(2)
                        e_nome = c1.text_input("Nome", value=m_dados["nome"])
                        e_cpf = c2.text_input(
                            "CPF / Matrícula", value=m_dados["cpf_matricula"]
                        )

                        c3, c4, c5 = st.columns(3)
                        e_tel = c3.text_input(
                            "Telefone", value=m_dados.get("telefone", "")
                        )
                        e_cnh = c4.text_input(
                            "CNH", value=m_dados.get("cnh", "")
                        )

                        cats = [
                            "A",
                            "B",
                            "C",
                            "D",
                            "E",
                            "AB",
                            "AC",
                            "AD",
                            "AE",
                        ]
                        e_cat = c5.selectbox(
                            "Categoria CNH",
                            cats,
                            index=cats.index(m_dados.get("categoria_cnh"))
                            if m_dados.get("categoria_cnh") in cats
                            else 1,
                        )

                        e_status = st.selectbox(
                            "Status",
                            ["Ativo", "Inativo"],
                            index=0
                            if m_dados.get("status") == "Ativo"
                            else 1,
                        )

                        if st.form_submit_button("Atualizar Motorista"):
                            atualizar_motorista(
                                m_dados["id"],
                                e_nome,
                                e_cpf,
                                e_tel,
                                e_cnh,
                                e_cat,
                                datetime.date.today(),
                                e_status,
                            )
                            st.success("Motorista atualizado!")
                            st.rerun()

        elif opcao == "Checklist":
            render_checklist()

        elif opcao == "Manutenções":
            render_manutencoes()
