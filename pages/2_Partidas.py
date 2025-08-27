import streamlit as st, pandas as pd
from core import api_client
st.title("📅 Partidas")

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
fx = api_client.fixtures(team["team_id"], season)

rows=[]
for it in fx:
    f = it["fixture"]; lg = it["league"]; th = it["teams"]["home"]; ta = it["teams"]["away"]; goals = it["goals"]
    rows.append({
        "fixture_id": f["id"], "date": f["date"], "status": f["status"]["short"],
        "league": lg["name"], "round": lg.get("round"),
        "home": th["name"], "home_logo": th["logo"],
        "away": ta["name"], "away_logo": ta["logo"],
        "goals_home": goals["home"], "goals_away": goals["away"]
    })
df = pd.DataFrame(rows).sort_values("date")
for _, r in df.iterrows():
    c1,c2,c3,c4 = st.columns([1,3,1,3])
    with c1: st.image(r["home_logo"], width=32)
    with c2: st.write(f"{r['home']}")
    with c3: st.write(f"**{r['goals_home']} : {r['goals_away']}**" if r['goals_home'] is not None else r['status'])
    with c4: 
        st.image(r["away_logo"], width=32)
        st.write(r["away"])
