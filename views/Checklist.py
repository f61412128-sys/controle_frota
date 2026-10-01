import json
import sqlite3
import time
import urllib.request
import pandas as pd
import streamlit as st
from config import DB_PATH
from views.services.cadastros_service import listar_motoristas, listar_veiculos


def obter_endereco_reverso(lat_lon_str):
  """Converte coordenadas (latitude, longitude) num endereço legível (rua, bairro, cidade)."""
  try:
    if (
        not lat_lon_str
        or "," not in lat_lon_str
        or "Negado" in lat_lon_str
        or "Aguardando" in lat_lon_str
    ):
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

    with urllib.request.urlopen(req, timeout=4) as response:
      data = json.loads(response.read().decode())
      if "display_name" in data:
        return data["display_name"]
  except Exception:
    pass

  return lat_lon_str


def salvar_checklist(
    veiculo_id,
    motorista_id,
    km,
    itens_respostas,
    observacoes,
    foto_bytes,
    localizacao,
):
  # Converte as coordenadas em endereço legível
  localizacao_amigavel = obter_endereco_reverso(localizacao)

  with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()

    # Garante compatibilidade caso a coluna localizacao ainda não exista
    cursor.execute("PRAGMA table_info(checklists)")
    colunas_chk = [col[1] for col in cursor.fetchall()]
    if "localizacao" not in colunas_chk:
      try:
        cursor.execute("ALTER TABLE checklists ADD COLUMN localizacao TEXT")
      except Exception:
        pass

    # 1. Determina resultado geral
    tem_pendencia = any(res == "NÃO OK" for res in itens_respostas.values())
    resultado_geral = "Com pendências" if tem_pendencia else "Aprovado"

    # 2. Salva o Checklist com o endereço amigável
    cursor.execute(
        """
        INSERT INTO checklists (veiculo_id, motorista_id, km, resultado, observacoes, localizacao)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            veiculo_id,
            motorista_id if motorista_id else 1,
            km,
            resultado_geral,
            observacoes,
            localizacao_amigavel,
        ),
    )
    checklist_id = cursor.lastrowid

    # 3. Salva os Itens e abre Ocorrências automáticas se houver falha
    for (categoria, item), resp in itens_respostas.items():
      cursor.execute(
          """
            INSERT INTO itens_checklist (checklist_id, categoria, item, resultado)
            VALUES (?, ?, ?, ?)
            """,
          (checklist_id, categoria, item, resp),
      )

      if resp == "NÃO OK":
        cursor.execute("PRAGMA table_info(ocorrencias)")
        colunas_oco = [col[1] for col in cursor.fetchall()]

        val_oco = {
            "veiculo_id": veiculo_id,
            "motorista_id": motorista_id if motorista_id else 1,
            "checklist_id": checklist_id,
            "item": item,
            "descricao": (
                f"Avaria apontada no checklist (Local: {localizacao_amigavel}):"
                f" {item}"
            ),
            "status": "Aberto",
        }
        if "gravidade" in colunas_oco:
          val_oco["gravidade"] = "Média"

        cols = ", ".join(val_oco.keys())
        placeholders = ", ".join(["?"] * len(val_oco))
        cursor.execute(
            f"INSERT INTO ocorrencias ({cols}) VALUES ({placeholders})",
            list(val_oco.values()),
        )

    # 4. Atualiza o KM do veículo
    cursor.execute(
        "UPDATE veiculos SET km_atual = ? WHERE id = ?", (km, veiculo_id)
    )
    conn.commit()


def buscar_historico_checklists():
  """Consulta o histórico de checklists de forma segura, adaptando-se às colunas reais da BD."""
  with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(checklists)")
    colunas_chk = [col[1] for col in cursor.fetchall()]

    col_data_sql = "''"
    if "created_at" in colunas_chk:
      col_data_sql = "c.created_at"
    elif "data" in colunas_chk:
      col_data_sql = "c.data"

    col_loc_sql = (
        "c.localizacao" if "localizacao" in colunas_chk else "'' AS localizacao"
    )

    query = f"""
            SELECT 
                c.id,
                {col_data_sql} AS created_at,
                c.km,
                c.resultado,
                c.observacoes,
                {col_loc_sql},
                v.placa,
                v.modelo,
                COALESCE(m.nome, u.nome, 'Não informado') AS motorista_nome
            FROM checklists c
            LEFT JOIN veiculos v ON c.veiculo_id = v.id
            LEFT JOIN motoristas m ON c.motorista_id = m.id
            LEFT JOIN usuarios u ON c.motorista_id = u.id
            ORDER BY c.id DESC
        """
    cursor.execute(query)
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


def buscar_itens_checklist(checklist_id):
  """Consulta os itens inspecionados de um determinado checklist."""
  with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT categoria, item, resultado FROM itens_checklist WHERE"
        " checklist_id = ?",
        (checklist_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


def render():
  st.title("📲 Checklist Diário")

  tab_novo, tab_historico = st.tabs(
      ["📝 Preencher Checklist", "📊 Histórico & Consultas"]
  )

  # -------------------------------------------------------------------------
  # ABA 1: FORMULÁRIO DE NOVO CHECKLIST
  # -------------------------------------------------------------------------
  with tab_novo:
    st.caption("Preencha a inspeção do veículo de forma rápida.")

    veiculos = listar_veiculos()

    if not veiculos:
      st.warning(
          "É necessário ter veículos cadastrados no sistema para realizar o"
          " checklist."
      )
      return

    mapa_v = {
        f"{v['placa']} - {v['modelo']}": (v["id"], v["km_atual"])
        for v in veiculos
    }

    usuario_nome = st.session_state.get("usuario_nome", "Motorista")
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
                    { maximumAge: 0, timeout: 15000, enableHighAccuracy: true }
                );
            }
        }
        pegarGPS();
        setInterval(pegarGPS, 3000);
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

      st.text_input("Motorista Responsável", value=usuario_nome, disabled=True)

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

        # Bloco de segurança: se o motorista enviou muito rápido e o GPS ainda não respondeu,
        # damos 2 segundos de folga para a query param atualizar na thread.
        tentativa = 0
        loc_atual = st.query_params.get("gps_auto", "Aguardando sinal de GPS...")
        while "Aguardando" in loc_atual and tentativa < 4:
          time.sleep(0.5)
          loc_atual = st.query_params.get(
              "gps_auto", "Aguardando sinal de GPS..."
          )
          tentativa += 1

        try:
          salvar_checklist(
              veiculo_id,
              motorista_id,
              km,
              respostas,
              obs,
              foto_bytes,
              loc_atual,
          )
          st.success("Checklist enviado com sucesso!")
          st.balloons()
        except Exception as e:
          st.error(f"Erro ao salvar checklist: {e}")

  # -------------------------------------------------------------------------
  # ABA 2: HISTÓRICO DE REGISTROS (ÁREA EXCLUSIVA PARA ADMIN / CONSULTAS)
  # -------------------------------------------------------------------------
  with tab_historico:
    st.caption(
        "Consulte os históricos de vistorias, avarias e localização exata"
        " reportada."
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

      titulo_card = (
          f"{status_icone} {reg['placa']} - {reg['modelo']}{loc_txt} |"
          f" {data_formatada}"
      )

      with st.expander(titulo_card):
        st.write(f"**Motorista:** {reg['motorista_nome']}")
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
          st.error("⚠️️ **Itens com Avaria:**")
          for item_f in itens_falha:
            st.write(
                f"- **{item_f['categoria']} - {item_f['item']}**:"
                f" {item_f['resultado']}"
            )
        else:
          st.success("✅ Todos os itens foram aprovados nesta vistoria.")