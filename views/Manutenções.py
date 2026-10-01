import pandas as pd
import streamlit as st
from views.services.cadastros_service import (
    listar_veiculos,  # Crie ou use a função para buscar veículos
)


def render():
    st.title("🛠️ Controle de Manutenções")

    tab1, tab2, tab3 = st.tabs([
        "📋 Histórico",
        "➕ Nova Manutenção",
        "📊 Custos & Indicadores",
    ])

    with tab1:
        st.subheader("Manutenções Registradas")
        # Exemplo: Carregar dados via SQLite ou Pandas
        st.info("Lista de manutenções registradas na frota.")

    with tab2:
        st.subheader("Registrar Serviço / Revisão")

        veiculos = listar_veiculos()
        mapa_veiculos = {
            f"{v['placa']} - {v['modelo']}": v["id"] for v in veiculos
        }

        with st.form("form_manutencao", clear_on_submit=True):
            veiculo_sel = st.selectbox(
                "Veículo*", list(mapa_veiculos.keys()) if mapa_veiculos else []
            )

            col1, col2 = st.columns(2)
            tipo = col1.selectbox(
                "Tipo de Manutenção*", ["Preventiva", "Corretiva"]
            )
            status = col2.selectbox(
                "Status*", ["Concluída", "Em Andamento", "Agendada"]
            )

            descricao = st.text_area(
                "Descrição dos Serviços / Peças Trocadas*"
            )

            col3, col4, col5 = st.columns(3)
            oficina = col3.text_input("Oficina / Prestador")
            km_registro = col4.number_input("KM Atual do Veículo", min_value=0)
            custo = col5.number_input(
                "Custo Total (R$)", min_value=0.0, format="%.2f"
            )

            col6, col7 = st.columns(2)
            data_manut = col6.date_input("Data do Serviço")
            proximo_km = col7.number_input(
                "Próxima Revisão (KM)", min_value=0, value=km_registro + 10000
            )

            btn_salvar = st.form_submit_button("Salvar Manutenção")

            if btn_salvar:
                if veiculo_sel and descricao:
                    # Aqui chamamos a função para salvar no SQLite
                    st.success("Manutenção registrada com sucesso!")
                else:
                    st.warning("Preencha todos os campos obrigatórios.")

    with tab3:
        st.subheader("Resumo Financeiro da Frota")
        st.metric(label="Gasto Total em Manutenção", value="R$ 0,00")