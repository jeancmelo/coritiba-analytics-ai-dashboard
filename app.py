# app.py
import streamlit as st
from core import api_client

st.set_page_config(
    page_title="Coritiba Analytics AI — Dashboard",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Coritiba Analytics AI — Dashboard")
st.markdown("### Bem-vindo ao **Coritiba Analytics AI** 🚀")

st.markdown("""
Este projeto é um **MVP de dashboard inteligente** que combina dados do **API-Football**  
com análises de **Inteligência Artificial (OpenAI)** para oferecer insights em tempo real sobre o desempenho do **Coritiba Foot Ball Club**.

---

### 🔧 Tecnologias utilizadas
- **[Streamlit](https://streamlit.io/)** → Interface interativa e leve para dashboards.  
- **[API-Football](https://www.api-football.com/)** → Fonte de dados sobre partidas, times, ligas, estatísticas e jogadores.  
- **[OpenAI API](https://platform.openai.com/)** → Geração de insights automáticos, previsões e explicações em linguagem natural.  
- **Python (Pandas, Requests, Matplotlib, Plotly)** → Manipulação de dados e visualizações.

---

### 📊 Funcionalidades principais
- **Visão Geral** → Resumo da temporada, curiosidades e estatísticas-chave.  
- **Partidas** → Histórico dos jogos, estatísticas por partida, lineups e eventos.  
- **Desempenho do Time** → KPIs avançados, tendências, médias móveis e previsões.  
- **Elenco de Jogadores** → Detalhes individuais de desempenho (gols, assistências, cartões, minutos).  
- **Comparativos** → Comparações do Coritiba com rivais diretos e médias da liga.  
- **Adversário** → Scouting completo do próximo rival, com prévia tática e análise IA.  
- **Tendências & Alertas** → Detecção automática de variações de desempenho.  
- **Insights IA** → Central de inteligência com análises automáticas e interação por prompt.  

---

### 📈 Outputs do MVP
- Painel em tempo real do Coritiba na Série B 2025.  
- **Insights automáticos e explicações contextuais** geradas pela IA.  
- Comparativos e relatórios que podem ser exportados e compartilhados.  
- Base escalável para integrar outras ligas, times e temporadas.  

---

⚪🟢 **Força, Coxa!**
""")

# Exibir logo
team = api_client.find_team("Coritiba")
if team:
    st.image(team["team_logo"], width=120)
    st.subheader(team["team_name"])
    st.caption(f"Estádio: {team.get('venue_name','-')}")
