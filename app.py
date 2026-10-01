import base64
import datetime
import os
from pathlib import Path
import sqlite3
import sys

# Adiciona a pasta atual ao caminho do Python
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
    initial_sidebar_state="auto",
)

# Estilização CSS para Mobile / App e Correção da Sidebar
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .block-container {
        padding-top: 0.5rem;
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

    /* Correção total para mobile: garante que a sidebar abra por cima e ocupe o espaço correto sem quebrar */
    @media (max-width: 992px) {
        section[data-testid="stSidebar"] {
            width: 85vw !important;
            z-index: 999999 !important;
        }
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

# --- SESSÃO / LOGIN ---
if "logado" not in st.session_state:
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

            if usuario_db:
                st.session_state["logado"] = True
                st.session_state["perfil"] = usuario_db["perfil"]
                st.session_state["usuario_nome"] = (
                    usuario_db["login"].capitalize()
                )
                st.session_state["motorista_id"] = usuario_db["motorista_id"]
                st.rerun()
            elif usuario_input.lower() == "admin" and senha_input == "admin123":
                st.session_state["logado"] = True
                st.session_state["perfil"] = "admin"
                st.session_state["usuario_nome"] = "Administrador Mestre"
                st.session_state["motorista_id"] = None
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

else:
    # Sidebar
    LOGO_PATH = Path(__file__).parent / "nossoar.jpg"
    logo = (
        base64.b64encode(open(LOGO_PATH, "rb").read()).decode()
        if LOGO_PATH.exists()
        else ""
    )

    st.sidebar.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
            <img src="data:image/jpeg;base64,{logo}" style="height: 40px; width: auto;">
            <span style="font-size: 18px; font-weight: bold;">Controle de Frota</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.write(
        f"👤 **{st.session_state['usuario_nome']}** "
        f"({st.session_state['perfil'].upper()})"
    )

    if st.sidebar.button("🚪 Sair / Logout", use_container_width=True):
        st.session_state["logado"] = False
        st.session_state["perfil"] = None
        st.session_state["usuario_nome"] = ""
        st.session_state["motorista_id"] = None
        st.rerun()

    st.sidebar.divider()

    # --- PERFIL MOTORISTA ---
    if st.session_state["perfil"] == "motorista":
        st.sidebar.info("Modo Checklist (Celular)")
        render_checklist()

    # --- PERFIL ADMINISTRADOR ---
    elif st.session_state["perfil"] == "admin":
        opcao = st.sidebar.radio(
            "Navegação",
            [
                "Dashboard",
                "Gestão de Usuários",
                "Veículos",
                "Motoristas",
                "Checklist (Teste)",
                "Manutenções",
            ],
        )

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
                                opcoes_m.get(motorista_vinc),
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

                    # --- CAMPOS DE PROPRIEDADE ---
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
                                placa,
                                marca,
                                modelo,
                                ano,
                                tipo,
                                cor,
                                chassi,
                                km_atual,
                                opcoes_motoristas.get(motorista_sel),
                                tipo_propriedade,
                                locadora if tipo_propriedade != "Próprio" else None,
                                inicio_contrato
                                if tipo_propriedade != "Próprio"
                                else None,
                                fim_contrato
                                if tipo_propriedade != "Próprio"
                                else None,
                                valor_mensal
                                if tipo_propriedade != "Próprio"
                                else 0.0,
                            )
                            st.success("Veículo cadastrado!")
                            st.rerun()

            with tab_editar:
                if veiculos:
                    mapa_v = {
                        f"{v['placa']} - {v['modelo']}": dict(v)
                        for v in veiculos
                    }
                    v_dados = mapa_v[
                        st.selectbox(
                            "Selecione o Veículo para Editar",
                            list(mapa_v.keys()),
                        )
                    ]

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
                        e_tipo = c5.selectbox(
                            "Tipo",
                            tipos_list,
                            index=tipos_list.index(v_dados["tipo"])
                            if v_dados["tipo"] in tipos_list
                            else 0,
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

                        # --- EDITAR PROPRIEDADE ---
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
                        e_inicio_contrato = c11.date_input("Início do Contrato")
                        e_fim_contrato = c12.date_input("Fim do Contrato")
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
                                v_dados["id"],
                                e_placa,
                                e_marca,
                                e_modelo,
                                e_ano,
                                e_tipo,
                                e_cor,
                                e_chassi,
                                e_km,
                                opcoes_motoristas.get(e_motorista),
                                e_tipo_propriedade,
                                e_locadora,
                                e_inicio_contrato,
                                e_fim_contrato,
                                e_valor_mensal,
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

        elif opcao == "Checklist (Teste)":
            render_checklist()

        elif opcao == "Manutenções":
            render_manutencoes()
