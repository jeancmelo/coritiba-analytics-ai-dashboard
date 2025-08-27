import streamlit as st
import pandas as pd
from core import api_client, ui_utils, ai

st.title("🔎 Scouting do Adversário — Prévia do próximo jogo")

# filtros globais
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
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

st.caption("Análise do próximo adversário com estatísticas recentes + prévia IA.")

# buscar próximo jogo do Coxa
fixtures = api_client.fixtures(team["team_id"], season, next=1)
if not fixtures:
    st.info("Nenhum próximo jogo encontrado na API.")
    st.stop()

fx = fixtures[0]
fixture_id = fx["fixture"]["id"]
opponent = fx["teams"]["away"] if fx["teams"]["home"]["id"] == team["team_id"] else fx["teams"]["home"]

st.subheader(f"📅 Próximo adversário: **{opponent['name']}**")
ui_utils.load_image(opponent["logo"], size=72, alt=opponent["name"])

# estatísticas do adversário
opp_stats = api_client.team_statistics(league["league_id"], season, opponent["id"])
opp_stats = opp_stats[0] if isinstance(opp_stats, list) and opp_stats else opp_stats

if not opp_stats:
    st.warning("Não foi possível carregar estatísticas do adversário.")
    st.stop()

# forma recente (últimos 5 jogos)
opp_fixtures = api_client.fixtures(opponent["id"], season)
opp_last5 = sorted(opp_fixtures, key)
