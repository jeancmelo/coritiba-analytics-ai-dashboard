import streamlit as st
from core import api_client
import pandas as pd
st.title("📊 Visão Geral")

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")
if not league:
    st.error("Liga não detectada para a temporada selecionada.")
    st.stop()

stats = api_client.team_statistics(league["league_id"], season, team["team_id"])
stats = stats[0] if isinstance(stats, list) and stats else stats

col1, col2 = st.columns(2)
with col1:
    st.metric("Vitórias", stats["fixtures"]["wins"]["total"])
    st.metric("Derrotas", stats["fixtures"]["loses"]["total"])
with col2:
    st.metric("Gols Pró", stats["goals"]["for"]["total"]["total"])
    st.metric("Gols Contra", stats["goals"]["against"]["total"]["total"])

st.caption("Fonte: API-Football")
