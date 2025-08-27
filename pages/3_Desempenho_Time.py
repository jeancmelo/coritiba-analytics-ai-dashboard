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
if not ts:
    st.warning("Sem estatísticas disponíveis.")
    st.stop()

gf = (ts.get("goals") or {}).get("for", {}).get("minute") or {}
ga = (ts.get("goals") or {}).get("against", {}).get("minute") or {}

def df_minute(d):
    rows=[]
    for k,v in d.items():
        rows.append({"minuto": k, "total": (v or {}).get("total") or 0})
    return pd.DataFrame(rows)

c1,c2 = st.columns(2)
with c1:
    st.subheader("Gols Pró por faixa")
    st.plotly_chart(px.bar(df_minute(gf), x="minuto", y="total"), use_container_width=True)
with c2:
    st.subheader("Gols Contra por faixa")
    st.plotly_chart(px.bar(df_minute(ga), x="minuto", y="total"), use_container_width=True)
