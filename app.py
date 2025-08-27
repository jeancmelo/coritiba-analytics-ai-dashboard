import streamlit as st
from core import api_client

st.set_page_config("Coritiba Analytics AI", page_icon="✅", layout="wide")

st.title("Coritiba Analytics AI — Dashboard")

st.markdown("""
Bem-vindo ao **Coritiba Analytics AI** 🚀

Use o menu lateral para navegar pelas páginas:
- Visão Geral
- Partidas
- Desempenho do Time
- Elenco e Jogadores
- Comparativos
- Adversário
- Tendências & Alertas
- Insights com IA
""")

team = api_client.find_team("Coritiba")
col1, col2 = st.columns([1,3])
with col1:
    st.image(team["team_logo"], width=96)
with col2:
    st.subheader(team["team_name"])
    st.caption(f"Estádio: {team['venue'].get('name')}")
