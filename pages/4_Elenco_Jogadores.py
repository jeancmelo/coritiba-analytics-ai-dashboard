import streamlit as st
from core import api_client
st.title("🧑‍🤝‍🧑 Elenco & Jogadores")

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
pls = api_client.api_get("players", {"team": team["team_id"], "season": season, "page": 1})

if not pls:
    st.warning("Sem dados de jogadores para esta temporada/página.")
else:
    for p in pls:
        player = p.get("player", {})
        stats = (p.get("statistics") or [{}])[0]
        c1,c2 = st.columns([1,4])
        with c1:
            if player.get("photo"):
                st.image(player["photo"], width=56)
        with c2:
            st.write(f"**{player.get('name','Jogador')}** — {stats.get('games',{}).get('position','-')}")
            st.caption(f"Minutos: {stats.get('games',{}).get('minutes','-')} • Gols: {stats.get('goals',{}).get('total','-')} • Assist.: {stats.get('goals',{}).get('assists','-')}")
