import streamlit as st, pandas as pd
from core import api_client
st.title("⚔️ Comparativos (Liga & Rivais)")

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")
if not league:
    st.error("Liga não detectada para a temporada selecionada.")
    st.stop()

std = api_client.standings(league["league_id"], season)
table = std[0]["league"]["standings"][0]
rows=[]
for row in table:
    t = row["team"]
    all_ = row["all"]
    rows.append({
        "rank": row["rank"],
        "team": t["name"],
        "logo": t["logo"],
        "played": all_["played"],
        "win": all_["win"],
        "draw": all_["draw"],
        "lose": all_["lose"],
        "points": row["points"],
        "goalsDiff": row["goalsDiff"]
    })
df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)
