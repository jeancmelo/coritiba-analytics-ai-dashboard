import streamlit as st
import pandas as pd
from core import api_client, ui_utils

st.title("📅 Partidas — Calendário & Detalhes")

# --------------------------------------------
# Filtros e cabeçalho
# --------------------------------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

# --------------------------------------------
# Carregamento de fixtures (uma vez)
# --------------------------------------------
fixtures = api_client.fixtures(team["team_id"], season)
if not fixtures:
    st.warning("Nenhuma partida encontrada para os filtros atuais.")
    st.stop()

# ordena da mais recente para a mais antiga
for it in fixtures:
    it["_date"] = pd.to_datetime(it["fixture"]["date"], errors="coerce")
fixtures = sorted(fixtures, key=lambda x: x.get("_date") or pd.Timestamp(0), reverse=True)

# --------------------------------------------
# Filtro: Somente disputados / Somente futuros / Todos
# --------------------------------------------
def is_played(fx) -> bool:
    stt = (fx["fixture"].get("status") or {}).get("short", "")
    # finalizados pela API: FT, AET, PEN (e às vezes "FT" como long)
    return stt in {"FT", "AET", "PEN"}

def is_future(fx) -> bool:
    stt = (fx["fixture"].get("status") or {}).get("short", "")
    return stt in {"NS", "PST", "TBD"}  # not started / postponed / to be defined

mostrar = st.sidebar.selectbox(
    "Mostrar",
    ["Somente já disputados", "Somente futuros", "Todos"],
    index=0
)

if mostrar == "Somente já disputados":
    fixtures = [f for f in fixtures if is_played(f)]
elif mostrar == "Somente futuros":
    fixtures = [f for f in fixtures if is_future(f)]
# (se "Todos", mantém a lista)

# --------------------------------------------
# Paginação incremental (10 por vez)
# --------------------------------------------
key_n = f"n_rows_{season}_{mostrar.replace(' ','_')}"
if key_n not in st.session_state:
    st.session_state[key_n] = 10  # mostra 10 inicialmente

show_n = st.session_state[key_n]
fixtures_view = fixtures[:show_n]

# Botão "carregar mais"
colm1, colm2 = st.columns([1, 6])
with colm1:
    if st.button("Carregar mais 10", use_container_width=True):
        st.session_state[key_n] = min(show_n + 10, len(fixtures))
        st.experimental_rerun()
with colm2:
    st.caption(f"Mostrando {min(show_n, len(fixtures))} de {len(fixtures)} jogos ({mostrar.lower()}).")

st.divider()

# --------------------------------------------
# Render por jogo (somente os N exibidos)
# --------------------------------------------
OUR_ID = team["team_id"]

def _stats_to_df(blocks):
    """Converte /fixtures/statistics em dois DataFrames (nosso time x adversário)."""
    if not blocks:
        return None, None, None, None
    me = None; opp = None
    for b in blocks:
        tid = (b.get("team") or {}).get("id")
        if tid == OUR_ID:
            me = b
        else:
            opp = b
    if not me and not opp:
        return None, None, None, None

    def to_df(b):
        if not b:
            return pd.DataFrame(columns=["Métrica","Valor"])
        rows = []
        for it in (b.get("statistics") or []):
            t = it.get("type")
            v = it.get("value")
            # normaliza % que vem como string "55%"
            if isinstance(v, str) and v.endswith("%"):
                try:
                    v = float(v.replace("%","").strip())
                except Exception:
                    pass
            rows.append({"Métrica": t, "Valor": v})
        return pd.DataFrame(rows)

    df_me = to_df(me)
    df_opp = to_df(opp)
    me_name = (me or {}).get("team", {}).get("name")
    opp_name = (opp or {}).get("team", {}).get("name")
    return df_me, df_opp, me_name, opp_name

for fx in fixtures_view:
    f = fx["fixture"]
    lg = fx["league"]
    home = fx["teams"]["home"]; away = fx["teams"]["away"]
    is_home = (home["id"] == OUR_ID)
    gh, ga = fx["goals"]["home"], fx["goals"]["away"]

    # hero do jogo
    hero = st.container()
    cL, cT, cR = hero.columns([3, 4, 3])
    with cL:
        ui_utils.load_image(home["logo"], size=40, alt=home["name"])
        st.markdown(f"**{home['name']}**")
    with cT:
        score_txt = f"{int(gh)} : {int(ga)}" if gh is not None and ga is not None else f"{f['status']['short']}"
        st.markdown(f"<h2 style='text-align:center;margin:0'>{score_txt}</h2>", unsafe_allow_html=True)
        st.caption(f"<p style='text-align:center;margin:0'>{pd.to_datetime(f['date']).strftime('%d/%m/%Y %H:%M')}</p>", unsafe_allow_html=True)
    with cR:
        ui_utils.load_image(away["logo"], size=40, alt=away["name"])
        st.markdown(f"**{away['name']}**")

    meta1, meta2 = st.columns([2, 2])
    with meta1:
        st.caption(f"Liga: {lg.get('name')} • {lg.get('round')}")
    with meta2:
        st.caption(f"Status: {f.get('status',{}).get('long','-')}")

    # detalhes sob demanda
    with st.expander("Ver detalhes"):
        # ----------------------------
        # Estatísticas (formatadas)
        # ----------------------------
        st.markdown("**Estatísticas do jogo**")
        try:
            blocks = api_client.fixture_statistics(f["id"])
        except Exception:
            blocks = []

        df_me, df_opp, me_name, opp_name = _stats_to_df(blocks)
        if df_me is not None:
            cs1, cs2 = st.columns(2)
            with cs1:
                st.markdown(f"**{me_name or 'Nosso time'}**")
                if df_me.empty:
                    st.info("Sem estatísticas do nosso time.")
                else:
                    st.dataframe(df_me, use_container_width=True, hide_index=True)
            with cs2:
                st.markdown(f"**{opp_name or 'Adversário'}**")
                if df_opp.empty:
                    st.info("Sem estatísticas do adversário.")
                else:
                    st.dataframe(df_opp, use_container_width=True, hide_index=True)
        else:
            st.info("Sem estatísticas disponíveis para este jogo.")

        st.markdown("---")

        # ----------------------------
        # Eventos (timeline simples)
        # ----------------------------
        st.markdown("**Eventos (timeline)**")
        try:
            evs = api_client.fixture_events(f["id"])
        except Exception:
            evs = []

        if evs:
            for ev in evs:
                minute = ev.get("time", {}).get("elapsed")
                tname = ev.get("team", {}).get("name")
                player = (ev.get("player") or {}).get("name") or "-"
                etype = ev.get("type") or "-"
                detail = ev.get("detail") or ""
                st.write(f"- {minute}' • {tname}: {etype} {f'({detail})' if detail else ''} — {player}")
        else:
            st.info("Sem eventos disponíveis.")

        st.markdown("---")

        # ----------------------------
        # Lineups (grade de titulares)
        # ----------------------------
        st.markdown("**Lineups & formações**")
        try:
            lineups = api_client.fixture_lineups(f["id"])
        except Exception:
            lineups = []

        if not lineups:
            st.info("Sem lineups disponíveis.")
        else:
            for block in lineups:
                tname = (block.get("team") or {}).get("name")
                tlogo = (block.get("team") or {}).get("logo")
                form = block.get("formation") or "?"
                st.markdown(f"**{tname}** — formação: `{form}`")
                ui_utils.load_image(tlogo, size=28, alt=f"Logo {tname}")

                start11 = block.get("startXI") or []
                if start11:
                    st.caption("Titulares:")
                    grid_cols = st.columns(4)
                    i = 0
                    for pl in start11:
                        p = pl.get("player", {}) or {}
                        with grid_cols[i % 4]:
                            st.write(p.get("name") or "-")
                        i += 1
                else:
                    st.info("Titulares não informados.")

    st.markdown("---")
