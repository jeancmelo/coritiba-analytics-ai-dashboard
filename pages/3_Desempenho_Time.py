import streamlit as st
import pandas as pd
import plotly.express as px
from core import api_client, ui_utils

st.title("📈 Desempenho do Time — Série B")

# filtro global
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

# time e liga (fixos pelo api_client)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

# header com logos
h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("KPIs agregados da temporada na Série B.")

# estatísticas do time (fixo: league 72, team 147)
ts = api_client.team_statistics(league["league_id"], season, team["team_id"])
ts = ts[0] if isinstance(ts, list) and ts else ts

if not ts:
    st.warning("Sem estatísticas disponíveis para esta temporada.")
    st.stop()

# Gols por minuto (pró e contra)
gf = (ts.get("goals") or {}).get("for", {}).get("minute") or {}
ga = (ts.get("goals") or {}).get("against", {}).get("minute") or {}

def df_minute(d):
    rows = []
    for k, v in d.items():
        rows.append({
            "minuto": k,
            "total": (v or {}).get("total") or 0
        })
    return pd.DataFrame(rows)

# KPIs extras
shots = ts.get("shots", {})
passes = ts.get("passes", {})
duels = ts.get("duels", {})
clean_sheets = ts.get("clean_sheet", {})

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Média de Chutes/Jogo", shots.get("total", {}).get("average", 0))
kpi2.metric("Posse Média (%)", ts.get("possession", {}).get("average", "-"))
kpi3.metric("Passes certos %", passes.get("accuracy", {}).get("percentage", "-"))
kpi4.metric("Clean Sheets", clean_sheets.get("total", 0))

st.divider()

c1, c2 = st.columns(2)
with c1:
    st.subheader("⚽ Gols Pró por faixa de minuto")
    df_gf = df_minute(gf)
    if not df_gf.empty:
        st.plotly_chart(px.bar(df_gf, x="min
