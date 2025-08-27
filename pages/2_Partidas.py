import streamlit as st
import pandas as pd
from core import api_client, ui_utils

st.title("📅 Partidas — Calendário & Detalhes")

# filtros globais
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

# header com logos
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

header1, header2, header3 = st.columns([1,4,1])
with header1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with header2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with header3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

# lista de partidas
fx = api_client.fixtures(team["team_id"], season)
if not fx:
    st.warning("Nenhuma partida encontrada para os filtros atuais.")
    st.stop()

rows=[]
for it in fx:
    f = it["fixture"]
    lg = it["league"]
    th = it["teams"]["home"]
    ta = it["teams"]["away"]
    goals = it["goals"]
    rows.append({
        "fixture_id": f["id"],
        "date": f["date"],
        "status": f["status"]["short"],
        "league": lg["name"],
        "round": lg.get("round"),
        "home": th["name"], "home_logo": th["logo"], "home_id": th["id"],
        "away": ta["name"], "away_logo": ta["logo"], "away_id": ta["id"],
        "goals_home": goals["home"], "goals_away": goals["away"]
    })

df = pd.DataFrame(rows).sort_values("date")
df["date"] = pd.to_datetime(df["date"])

st.divider()
st.caption("Clique em uma partida para abrir detalhes (estatísticas, eventos, lineups).")

# render linha a linha com logos e botão de detalhes
for _, r in df.iterrows():
    box = st.container()
    c1, c2, cscore, c3 = box.columns([2, 5, 2, 5])

    with c1:
        ui_utils.load_image(r["home_logo"], size=32, alt=f"Logo {r['home']}")
    with c2:
        st.write(f"**{r['home']}**")

    with cscore:
        if pd.notna(r["goals_home"]):
            st.write(f"**{int(r['goals_home'])} : {int(r['goals_away'])}**")
        else:
            st.write(r["status"])

    with c3:
        row1, row2 = st.columns([1, 7])
        with row1:
            ui_utils.load_image(r["away_logo"], size=32, alt=f"Logo {r['away']}")
        with row2:
            st.write(f"**{r['away']}**")

    meta1, meta2, meta3 = box.columns([3, 3, 2])
    with meta1:
        st.caption(f"Data: {r['date'].strftime('%d/%m/%Y %H:%M')}")
    with meta2:
        st.caption(f"Liga: {r['league']} • {r['round']}")
    with meta3:
        # abre um drawer-like usando expander para detalhes
        with st.expander("Ver detalhes"):
            # Estatísticas do jogo
            st.markdown("**Estatísticas do Jogo**")
            try:
                fstats = api_client.fixture_statistics(int(r["fixture_id"]))
                if fstats:
                    st.write(fstats)
                else:
                    st.info("Sem estatísticas disponíveis para este fixture.")
            except Exception as e:
                st.warning(f"Falha ao carregar estatísticas: {e}")

            # Eventos do jogo
            st.markdown("**Eventos (timeline)**")
            try:
                fevents = api_client.fixture_events(int(r["fixture_id"]))
                if fevents:
                    # render simples por enquanto
                    for ev in fevents:
                        time = ev.get("time", {}).get("elapsed")
                        team_name = ev.get("team", {}).get("name")
                        player = ev.get("player", {}).get("name")
                        etype = ev.get("type")
                        detail = ev.get("detail")
                        st.write(f"- {time}' • {team_name}: {etype} ({detail}) — {player}")
                else:
                    st.info("Sem eventos disponíveis.")
            except Exception as e:
                st.warning(f"Falha ao carregar eventos: {e}")

            # Lineups
            st.markdown("**Lineups & Formações**")
            try:
                fl = api_client.fixture_lineups(int(r["fixture_id"]))
                if fl:
                    for block in fl:
                        tname = block.get("team", {}).get("name")
                        tlogo = block.get("team", {}).get("logo")
                        form = block.get("formation")
                        st.write(f"**{tname}** — formação: `{form}`")
                        ui_utils.load_image(tlogo, size=24, alt=f"Logo {tname}")
                        start11 = block.get("startXI") or []
                        if start11:
                            st.caption("Titulares:")
                            cols = st.columns(6)
                            i = 0
                            for pl in start11:
                                p = pl.get("player", {})
                                with cols[i % 6]:
                                    st.write(p.get("name"))
                                i += 1
                else:
                    st.info("Sem lineups disponíveis.")
            except Exception as e:
                st.warning(f"Falha ao carregar lineups: {e}")

    st.markdown("---")
