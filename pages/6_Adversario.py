import streamlit as st, pandas as pd
from core import api_client
st.title("🔍 Scouting do Adversário")

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
fx = api_client.fixtures(team["team_id"], season, next=1)
if not fx:
    st.info("Sem próximo jogo disponível.")
    st.stop()

m = fx[0]
home, away = m["teams"]["home"], m["teams"]["away"]
is_home = (home["id"] == team["team_id"])
opp = away if is_home else home
st.subheader(f"Próximo adversário: {opp['name']}")
st.image(opp["logo"], width=64)
st.caption(f"Data: {m['fixture']['date']}")

league_id = m["league"]["id"]
opp_stats = api_client.team_statistics(league_id, season, opp["id"])
opp_stats = opp_stats[0] if isinstance(opp_stats, list) and opp_stats else opp_stats

if not opp_stats:
    st.warning("Sem estatísticas para o adversário.")
else:
    gf_total = opp_stats.get("goals",{}).get("for",{}).get("total",{}).get("total")
    ga_total = opp_stats.get("goals",{}).get("against",{}).get("total",{}).get("total")
    c1,c2 = st.columns(2)
    c1.metric("Gols Pró (temp.)", gf_total)
    c2.metric("Gols Contra (temp.)", ga_total)
    st.expander("Ver JSON bruto").write(opp_stats)
