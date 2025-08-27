import streamlit as st, pandas as pd, plotly.express as px
from core import api_client
st.title("📈 Desempenho do Time")

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")
if not league:
    st.error("Liga não detectada para a temporada selecionada.")
    st.stop()

ts = api_client.team_statistics(league["league_id"], season, team["team_id"])
ts = ts[0] if isinstance(ts, list) and ts else ts

gf = ts["goals"]["for"]["minute"]
ga = ts["goals"]["against"]["minute"]
def df_minute(d):
    out=[]
    for k,v in d.items():
        out.append({"minuto": k, "total": (v or {}).get("total") or 0})
    return pd.DataFrame(out)

st.subheader("Gols por faixa de minuto")
c1,c2 = st.columns(2)
with c1:
    fig = px.bar(df_minute(gf), x="minuto", y="total", title="Gols Pró")
    st.plotly_chart(fig, use_container_width=True)
with c2:
    fig2 = px.bar(df_minute(ga), x="minuto", y="total", title="Gols Contra")
    st.plotly_chart(fig2, use_container_width=True)
