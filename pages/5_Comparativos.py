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
if not std:
    st.warning("Sem standings retornadas.")
    st.stop()

table = std[0]["league"]["standings"][0]
rows=[]
for row in table:
    t = row["team"]; all_ = row["all"]
    rows.append({
        "rank": row["rank"],
        "escudo": t["logo"],
        "time": t["name"],
        "J": all_["played"],
        "V": all_["win"],
        "E": all_["draw"],
        "D": all_["lose"],
        "Pts": row["points"],
        "SG": row["goalsDiff"]
    })
df = pd.DataFrame(rows)

st.dataframe(
    df,
    use_container_width=True,
    column_config={
        "escudo": st.column_config.ImageColumn("escudo", width="small"),
    },
    hide_index=True
)
