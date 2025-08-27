import streamlit as st
import pandas as pd
from core import api_client, ui_utils

st.title("📅 Partidas — Calendário & Detalhes")

# ---- filtros globais
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

# ---- header com logos
header1, header2, header3 = st.columns([1, 4, 1])
with header1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with header2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with header3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

# ---- cache leve dos fixtures da temporada
@st.cache_data(show_spinner=False, ttl=300)
def _get_fixtures(team_id: int, season: int):
    fx = api_client.fixtures(team_id, season)
    for m in fx:
        m["_date"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
    fx = sorted(fx, key=lambda x: x.get("_date") or pd.Timestamp(0), reverse=True)
    return fx

fixtures = _get_fixtures(team["team_id"], season)
if not fixtures:
    st.warning("Nenhuma partida encontrada para os filtros atuais.")
    st.stop()

# ---- estado: quantos jogos mostrar
key_show = f"fx_show_{season}"
if key_show not in st.session_state:
    st.session_state[key_show] = 10

limit = st.session_state[key_show]
subset = fixtures[:limit]

st.caption("Clique em **Ver detalhes** para abrir estatísticas, eventos e lineups. Use o botão abaixo para carregar mais partidas.")

# ======================
# helpers de formatação
# ======================
STAT_KEYS = [
    ("Total Shots", "Chutes"),
    ("Shots on Goal", "SOT"),
    ("Ball Possession", "Posse (%)"),
    ("Corner Kicks", "Escanteios"),
    ("Fouls", "Faltas"),
    ("Offsides", "Impedimentos"),
    ("Yellow Cards", "Amarelos"),
    ("Red Cards", "Vermelhos"),
    ("Passes accurate", "Passes certos"),
]

def _to_num(v):
    if v is None: 
        return None
    if isinstance(v, str) and v.endswith("%"):
        try: 
            return float(v.replace("%", "").strip())
        except Exception: 
            return v
    try:
        return float(v)
    except Exception:
        return v

def _stats_table(stats_blocks):
    """Converte /fixtures/statistics em um DF Home x Away com chaves comuns."""
    if not stats_blocks: 
        return None
    # identifica quem é home e away pelas IDs do próprio bloco (o caller precisa informar?)
    # aqui só montamos dois dicionários (primeiro bloco = time A, segundo = time B)
    # e usamos os nomes entregues pela API
    rows = []
    teams = []
    for b in stats_blocks:
        tname = (b.get("team") or {}).get("name") or "Time"
        teams.append(tname)
        items = b.get("statistics") or []
        m = {}
        for api_key, label in STAT_KEYS:
            val = next((x.get("value") for x in items if (x.get("type") or "").lower() == api_key.lower()), None)
            m[label] = _to_num(val)
        rows.append(m)
    if len(rows) == 0:
        return None
    # monta tabela transposta (linhas = métricas, colunas = times)
    df = pd.DataFrame(rows, index=teams).T.reset_index().rename(columns={"index": "Métrica"})
    return df

def _render_lineup_grid(block, title="Lineup"):
    if not block:
        st.info("Sem lineups disponíveis.")
        return
    tname = (block.get("team") or {}).get("name")
    tlogo = (block.get("team") or {}).get("logo")
    form = block.get("formation") or "?"
    st.markdown(f"**{title}: {tname}** — formação `{form}`")
    if tlogo:
        ui_utils.load_image(tlogo, size=24, alt=f"Logo {tname}")
    start11 = block.get("startXI") or []
    if start11:
        st.caption("Titulares:")
        cols = st.columns(4)
        i = 0
        for pl in start11:
            p = pl.get("player", {}) or {}
            with cols[i % 4]:
                st.write(p.get("name") or "-")
            i += 1

def _events_list(events):
    if not events:
        st.info("Sem eventos disponíveis.")
        return
    # tabela compacta: minuto, time, tipo, detalhe, jogador
    rows = []
    for ev in events:
        minute = (ev.get("time") or {}).get("elapsed")
        tname = (ev.get("team") or {}).get("name")
        etype = ev.get("type")
        detail = ev.get("detail")
        player = (ev.get("player") or {}).get("name")
        rows.append({"Min": minute, "Time": tname, "Tipo": etype, "Detalhe": detail, "Jogador": player})
    df = pd.DataFrame(rows)
    df = df.sort_values("Min", kind="mergesort")
    st.dataframe(df, use_container_width=True, hide_index=True)

# ======================
# render por partida
# ======================
for fx in subset:
    f = fx["fixture"]
    lg = fx["league"]
    th = fx["teams"]["home"]; ta = fx["teams"]["away"]
    gh, ga = fx["goals"]["home"], fx["goals"]["away"]

    cont = st.container()
    topL, topC, topR = cont.columns([3, 3, 3])

    with topL:
        row = st.columns([1, 5, 1, 5])
        with row[0]:
            ui_utils.load_image(th["logo"], size=36, alt=th["name"])
        with row[1]:
            st.write(f"**{th['name']}**")
        with row[2]:
            ui_utils.load_image(ta["logo"], size=36, alt=ta["name"])
        with row[3]:
            st.write(f"**{ta['name']}**")

    with topC:
        if gh is not None and ga is not None:
            st.subheader(f"{int(gh)} : {int(ga)}")
        else:
            st.caption(f.get("status", {}).get("long") or f.get("status", {}).get("short", ""))

    with topR:
        st.caption(f"Data: {pd.to_datetime(f['date']).strftime('%d/%m/%Y %H:%M')}")
        st.caption(f"Liga: {lg['name']} • {lg.get('round','-')}")

    # ---- detalhes sob demanda
    with st.expander("Ver detalhes", expanded=False):
        colA, colB = st.columns([1, 2])

        with colA:
            st.markdown("**Estatísticas do jogo**")
            with st.spinner("Carregando estatísticas…"):
                try:
                    stats_blocks = api_client.fixture_statistics(int(f["id"]))
                except Exception:
                    stats_blocks = []
            df_stats = _stats_table(stats_blocks)
            if df_stats is not None and not df_stats.empty:
                st.dataframe(df_stats, use_container_width=True, hide_index=True)
            else:
                st.info("Estatísticas não disponíveis para este fixture.")

            st.markdown("**Eventos (timeline)**")
            with st.spinner("Carregando eventos…"):
                try:
                    events = api_client.fixture_events(int(f["id"]))
                except Exception:
                    events = []
            _events_list(events)

        with colB:
            st.markdown("**Lineups & Formações**")
            with st.spinner("Carregando lineups…"):
                try:
                    fl = api_client.fixture_lineups(int(f["id"]))
                except Exception:
                    fl = []
            if fl:
                # separa lineup do mandante e do visitante
                l_home = next((b for b in fl if (b.get("team") or {}).get("id") == th["id"]), None)
                l_away = next((b for b in fl if (b.get("team") or {}).get("id") == ta["id"]), None)
                _render_lineup_grid(l_home, title="Mandante")
                st.markdown("")  # espaçamento
                _render_lineup_grid(l_away, title="Visitante")
            else:
                st.info("Sem lineups disponíveis.")

    st.markdown("---")

# ---- paginação: carregar mais 10
remaining = max(len(fixtures) - limit, 0)
if remaining > 0:
    if st.button(f"Carregar mais {min(10, remaining)} partidas…"):
        st.session_state[key_show] += 10
        st.rerun()
else:
    st.caption("Você já visualizou todas as partidas desta temporada.")
