# pages/1_Visao_Geral.py
import streamlit as st
import random
from core import api_client

PAGE_TITLE = "📊 Visão Geral"
st.title(PAGE_TITLE)

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

c1, c2, c3 = st.columns([1, 4, 1])
with c1:
    st.image(team["team_logo"], width=72)
with c2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with c3:
    st.image(league["league_logo"], width=72)

st.markdown("---")

# Estatísticas rápidas
stats = api_client.team_statistics(league["league_id"], season, team["team_id"]) or {}
st.markdown("### ⚡ Resumo da temporada")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Vitórias", stats.get("wins",{}).get("total",{}).get("total","-"))
c2.metric("Derrotas", stats.get("loses",{}).get("total",{}).get("total","-"))
c3.metric("Gols Pró", stats.get("goals",{}).get("for",{}).get("total",{}).get("total","-"))
c4.metric("Gols Contra", stats.get("goals",{}).get("against",{}).get("total",{}).get("total","-"))

# Curiosidades fixas + dinâmicas
curiosidades = [
    "O **Coritiba Foot Ball Club** foi fundado em 1909 e é considerado o **clube mais antigo do futebol paranaense**.",
    "O Couto Pereira é o **maior estádio particular do Paraná**, com capacidade para mais de 37 mil torcedores.",
    "O Coritiba foi o **primeiro campeão brasileiro da região sul**, conquistando o Brasileirão em 1985.",
    "Em 2011, o Coxa entrou para o **Guinness Book** com a maior sequência de vitórias consecutivas (24) em competições oficiais.",
    "O mascote oficial é o **Vovô Coxa**, simbolizando tradição e pioneirismo no futebol."
]

st.markdown("### 🎲 Curiosidades do Coritiba")
st.info(random.choice(curiosidades))

# Destaques IA (placeholder para futura integração)
st.markdown("### 🤖 Insights IA sugeridos")
st.caption("Baseados no desempenho atual, a IA pode gerar destaques e comparações de temporada.")

st.markdown("- O Coxa tem aproveitamento superior jogando em casa.")
st.markdown("- Defesa consistente: destaque para clean sheets acumulados.")
st.markdown("- Ataque em evolução, tendência de crescimento no 2º turno.")

st.caption("Fonte: API-Football — Estatísticas gerais da equipe")
