import streamlit as st
import pandas as pd
from core import api_client, ui_utils

st.title("⚔️ Comparativos — Liga & Rivais")

# filtros globais
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

# header com logos (IDs fixos via api_client)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("Tabela da competição (standings) com KPIs básicos.")

# standings da Série B (ID fixo) na temporada selecionada
std = api_client.standings(league["league_id"], season)
if not std:
    st.warning("Standings não retornaram dados para essa temporada.")
    st.stop()

table = std[0]["league"]["standings"][0]

rows = []
for row in table:
    t = row["team"]
    all_ = row["all"]
    rows.append({
        "Pos": row["rank"],
        "Escudo": t["logo"],
        "Time": t["name"],
        "J": all_["played"],
        "V": all_["win"],
        "E": all_["draw"],
        "D": all_["lose"],
        "GP": all_["goals"]["for"],
        "GC": all_["goals"]["against"],
        "SG": row["goalsDiff"],
        "Pts": row["points"],
    })

df = pd.DataFrame(rows)

# Busca rápida por time
search = st.text_input("🔎 Buscar time", "")
if search:
    df_view = df[df["Time"].str.contains(search, case=False, na=False)].copy()
else:
    df_view = df.copy()

# Destaque visual do Coritiba
def highlight_coxa(row):
    return ['background-color: rgba(22, 163, 74, 0.15)' if row["Time"].lower().startswith("coritiba") else '' ] * len(row)

st.dataframe(
    df_view.style.apply(highlight_coxa, axis=1),
    use_container_width=True,
    column_config={
        "Escudo": st.column_config.ImageColumn("Escudo", width="small"),
        "Pos": st.column_config.NumberColumn("Pos", format="%d"),
        "Pts": st.column_config.NumberColumn("Pts", format="%d"),
        "SG": st.column_config.NumberColumn("SG", format="%d"),
        "J": st.column_config.NumberColumn("J", format="%d"),
        "V": st.column_config.NumberColumn("V", format="%d"),
        "E": st.column_config.NumberColumn("E", format="%d"),
        "D": st.column_config.NumberColumn("D", format="%d"),
        "GP": st.column_config.NumberColumn("GP", format="%d"),
        "GC": st.column_config.NumberColumn("GC", format="%d"),
    },
    hide_index=True
)

st.markdown("---")

# Comparativo rápido Coxa vs. um rival escolhido
times = df["Time"].tolist()
rival = st.selectbox("Comparar com rival", [t for t in times if t.lower() != "coritiba"])
coxa_row = df[df["Time"].str.lower() == "coritiba"].iloc[0]
rival_row = df[df["Time"] == rival].iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Pts (Coxa)", int(coxa_row["Pts"]), delta=int(coxa_row["Pts"] - int(rival_row["Pts"])))
c2.metric("SG (Coxa)", int(coxa_row["SG"]), delta=int(coxa_row["SG"] - int(rival_row["SG"])))
c3.metric("Vitórias (Coxa)", int(coxa_row["V"]), delta=int(coxa_row["V"] - int(rival_row["V"])))
c4.metric("GP (Coxa)", int(coxa_row["GP"]), delta=int(coxa_row["GP"] - int(rival_row["GP"])))
c5.metric("GC (Coxa)", int(coxa_row["GC"]), delta=int(coxa_row["GC"] - int(rival_row["GC"])))

st.caption("Fonte: API-Football — standings da Série B.")
