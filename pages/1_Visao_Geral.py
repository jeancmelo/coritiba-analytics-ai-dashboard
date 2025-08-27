import streamlit as st
from core import api_client

st.title("📊 Visão Geral")

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

if not league:
    st.error("Liga não detectada para a temporada selecionada.")
    st.stop()

ts = api_client.team_statistics(league["league_id"], season, team["team_id"])
ts = ts[0] if isinstance(ts, list) and ts else ts

if not ts:
    st.warning("Sem estatísticas agregadas para esta temporada/competição.")
    st.stop()

fixtures = ts.get("fixtures", {})
wins = fixtures.get("wins", {}).get("total", 0) or 0
loses = fixtures.get("loses", {}).get("total", 0) or 0
goals_for = ts.get("goals", {}).get("for", {}).get("total", {}).get("total", 0) or 0
goals_against = ts.get("goals", {}).get("against", {}).get("total", {}).get("total", 0) or 0

c1,c2,c3,c4 = st.columns(4)
c1.metric("Vitórias", wins)
c2.metric("Derrotas", loses)
c3.metric("Gols Pró", goals_for)
c4.metric("Gols Contra", goals_against)

st.caption("Fonte: API-Football")
