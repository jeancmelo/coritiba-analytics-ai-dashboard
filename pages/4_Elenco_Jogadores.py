import streamlit as st
import pandas as pd
from core import api_client, ui_utils

# IDs fixos (consistentes com core/api_client.py)
CORITIBA_ID = 147
SERIE_B_ID = 72

st.title("🧑‍🤝‍🧑 Elenco & Jogadores — Série B")

# ---------------------------------
# Filtros globais
# ---------------------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
only_with_minutes = st.sidebar.toggle("Somente quem atuou (minutos/aparições > 0)", value=False)
page = st.sidebar.number_input("Página (API)", min_value=1, value=1, step=1)

# Header com logos
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption(
    "Mostra jogadores que **possuem estatística na Série B (league.id = 72)** pelo Coritiba. "
    "Ative o toggle para exibir apenas quem de fato atuou (minutos/aparições > 0)."
)

# ---------------------------------
# Funções auxiliares
# ---------------------------------
def pick_serie_b_for_coxa(stats_list):
    """
    Retorna o dicionário 'statistics' correspondente à Série B (id=72) pelo Coritiba (id=147),
    se existir. Não exige minutos > 0 (isso é controlado no toggle).
    """
    if not stats_list:
        return None
    for s in stats_list:
        league = s.get("league", {}) or {}
        team_ = s.get("team", {}) or {}
        if league.get("id") == SERIE_B_ID and team_.get("id") == CORITIBA_ID:
            return s
    return None

# ---------------------------------
# Busca /players (paginado) e filtragem por Série B
# ---------------------------------
raw = api_client.api_get("players", {"team": team["team_id"], "season": season, "page": page})
if not raw:
    st.warning("Sem dados de jogadores para esta temporada/página. Tente outra página no seletor.")
    st.stop()

rows = []
for item in raw:
    player = item.get("player", {}) or {}
    stats_list = item.get("statistics") or []

    s = pick_serie_b_for_coxa(stats_list)
    if not s:
        # jogador não tem registro na Série B pelo Coxa -> não aparece
        continue

    games = s.get("games", {}) or {}
    goals = s.get("goals", {}) or {}
    shots = s.get("shots", {}) or {}
    passes = s.get("passes", {}) or {}
    duels = s.get("duels", {}) or {}
    cards = s.get("cards", {}) or {}

    minutes = games.get("minutes") or 0
    # API às vezes usa "appearences" e às vezes "appearances" (variações em payloads antigos)
    played = games.get("appearences") or games.get("appearances") or 0
    position = games.get("position") or "-"
    rating = games.get("rating")
    try:
        rating = float(rating) if rating else None
    except Exception:
        rating = None

    if only_with_minutes and (minutes <= 0 and played <= 0):
        # se a opção estiver ligada, exige contribuição em campo
        continue

    g_total = goals.get("total") or 0
    a_total = goals.get("assists") or 0
    sot = shots.get("on") or 0
    shots_total = shots.get("total") or 0
    key_passes = passes.get("key") or 0
    duels_won = duels.get("won") or 0
    duels_total = duels.get("total") or 0
    yc = cards.get("yellow") or 0
    rc = cards.get("red") or 0

    per90 = (minutes / 90) if minutes else 0
    g90 = (g_total / per90) if per90 else 0
    a90 = (a_total / per90) if per90 else 0
    sot90 = (sot / per90) if per90 else 0
    kp90 = (key_passes / per90) if per90 else 0
    duels_pct = (duels_won / duels_total * 100) if duels_total else None

    rows.append({
        "foto": player.get("photo"),
        "nome": player.get("name"),
        "idade": player.get("age"),
        "pos": position,
        "min": minutes,
        "jogos": played,
        "gols": g_total,
        "assist": a_total,
        "g90": round(g90, 2),
        "a90": round(a90, 2),
        "sot": sot,
        "sot90": round(sot90, 2),
        "keyP": key_passes,
        "kp90": round(kp90, 2),
        "duels%": round(duels_pct, 1) if duels_pct is not None else None,
        "YC": yc,
        "RC": rc,
        "rating": rating,
    })

df = pd.DataFrame(rows)

if df.empty:
    if only_with_minutes:
        st.info("Nenhum jogador com minutos/aparições na Série B nesta página. Desligue o toggle para ver todos com registro na Série B.")
    else:
        st.info("Nenhum jogador com registro na Série B nesta página. Tente mudar a página no seletor da sidebar.")
    st.stop()

# ---------------------------------
# Filtros de UI
# ---------------------------------
posicoes = ["Todos"] + sorted([p for p in df["pos"].dropna().unique() if p])
pos_sel = st.selectbox("Filtrar por posição", posicoes, index=0)

if pos_sel != "Todos":
    df_view = df[df["pos"] == pos_sel].copy()
else:
    df_view = df.copy()

ordens = {
    "Rating": "rating",
    "Gols": "gols",
    "Assistências": "assist",
    "Gols/90": "g90",
    "Assist./90": "a90",
    "SOT/90": "sot90",
    "Key passes/90": "kp90",
    "Minutos": "min",
}
ordem_sel = st.selectbox("Ordenar por", list(ordens.keys()), index=0)
asc = st.toggle("Ordem crescente?", value=False)
df_view = df_view.sort_values(ordens[ordem_sel], ascending=asc, na_position="last")

st.divider()

# ---------------------------------
# Render dos cards
# ---------------------------------
for _, r in df_view.iterrows():
    card = st.container()
    cimg, cmain, cnums = card.columns([1, 3, 3])

    with cimg:
        ui_utils.load_image(r["foto"], size=64, alt=r["nome"] or "Jogador")

    with cmain:
        st.markdown(f"**{r['nome'] or '—'}**")
        st.caption(f"{r['pos'] or '-'} • {int(r['idade']) if pd.notna(r['idade']) else '-'} anos")
        if r["rating"]:
            st.write(f"⭐ Rating: **{r['rating']}**")

    with cnums:
        m1, m2, m3 = st.columns(3)
        m1.metric("Gols", int(r["gols"]))
        m2.metric("Assist.", int(r["assist"]))
        m3.metric("Min", int(r["min"]))

        m4, m5, m6 = st.columns(3)
        m4.metric("G/90", r["g90"])
        m5.metric("A/90", r["a90"])
        m6.metric("SOT/90", r["sot90"])

        m7, m8, m9 = st.columns(3)
        m7.metric("KeyP/90", r["kp90"])
        m8.metric("Duelos %", r["duels%"] if pd.notna(r["duels%"]) else 0)
        m9.metric("Cartões", f"{int(r['YC'])}🟨 / {int(r['RC'])}🟥")

    st.markdown("---")

st.caption("Endpoint: /players?team=147&season=YYYY (filtrado por statistics.league.id=72 & statistics.team.id=147).")
