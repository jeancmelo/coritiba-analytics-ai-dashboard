import streamlit as st
import pandas as pd
import plotly.express as px
from core import api_client, ui_utils

st.title("📐 Táticas & Lineups — Série B")

# filtros globais
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

# time/league fixos
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

# header
h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("Frequência de formações, desempenho por esquema e análise de substituições.")

# -------------------------------------------------------------------
# Coleta fixtures + lineups
# -------------------------------------------------------------------
fixtures = api_client.fixtures(team["team_id"], season)
if not fixtures:
    st.info("Nenhuma partida encontrada.")
    st.stop()

rows = []
subs_rows = []
progress = st.progress(0)

OUR_ID = team["team_id"]

for i, fx in enumerate(fixtures, start=1):
    progress.progress(i / len(fixtures))
    fid = fx["fixture"]["id"]
    goals = fx["goals"]

    # resultado do jogo
    res = None
    if goals["home"] is not None and goals["away"] is not None:
        if (fx["teams"]["home"]["id"] == OUR_ID and goals["home"] > goals["away"]) or \
           (fx["teams"]["away"]["id"] == OUR_ID and goals["away"] > goals["home"]):
            res = "V"
        elif goals["home"] == goals["away"]:
            res = "E"
        else:
            res = "D"

    try:
        lineups = api_client.fixture_lineups(fid)
    except Exception:
        lineups = []

    # encontra lineup do Coxa
    lineup_block = None
    for b in lineups or []:
        if (b.get("team") or {}).get("id") == OUR_ID:
            lineup_block = b
            break

    if not lineup_block:
        continue

    formation = lineup_block.get("formation") or "?"
    coach = (lineup_block.get("coach") or {}).get("name")

    rows.append({
        "fixture_id": fid,
        "date": str(fx["fixture"]["date"])[:10],
        "formation": formation,
        "coach": coach,
        "res": res,
    })

    # processa substituições
    events = api_client.fixture_events(fid)
    for ev in events or []:
        if ev.get("type") == "subst":
            tid = (ev.get("team") or {}).get("id")
            if tid == OUR_ID:
                subs_rows.append({
                    "date": str(fx["fixture"]["date"])[:10],
                    "minute": ev.get("time", {}).get("elapsed"),
                    "player_out": (ev.get("player") or {}).get("name"),
                    "player_in": (ev.get("assist") or {}).get("name"),
                })

progress.empty()

df_form = pd.DataFrame(rows)
df_subs = pd.DataFrame(subs_rows)

# -------------------------------------------------------------------
# Análise de formações
# -------------------------------------------------------------------
st.markdown("### 📊 Formações utilizadas")
if df_form.empty:
    st.info("Nenhum dado de lineups disponível.")
else:
    counts = df_form.groupby("formation").size().reset_index(name="jogos")
    perf = df_form.groupby("formation")["res"].apply(lambda x: (x=="V").sum()).reset_index(name="vitórias")
    merged = pd.merge(counts, perf, on="formation", how="left")
    merged["aproveitamento_vit%"] = round(merged["vitórias"]/merged["jogos"]*100,1)

    st.dataframe(merged, use_container_width=True, hide_index=True)

    fig = px.bar(merged, x="formation", y="jogos", text="aproveitamento_vit%")
    fig.update_layout(yaxis_title="Nº de jogos", xaxis_title="Formação", title="Frequência e %Vitórias")
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------------
# Substituições
# -------------------------------------------------------------------
st.markdown("### 🔄 Substituições (minuto & jogadores)")
if df_subs.empty:
    st.info("Sem substituições registradas.")
else:
    st.dataframe(df_subs, use_container_width=True, hide_index=True)

    fig2 = px.histogram(df_subs, x="minute", nbins=12, title="Distribuição das substituições por minuto")
    fig2.update_layout(xaxis_title="Minuto do jogo", yaxis_title="Nº de subs")
    st.plotly_chart(fig2, use_container_width=True)

st.caption("Fonte: API-Football — /fixtures/lineups e /fixtures/events")
