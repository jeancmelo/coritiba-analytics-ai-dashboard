import streamlit as st
import pandas as pd
from core import api_client, ui_utils

# IDs fixos (mantém alinhado com core/api_client.py)
CORITIBA_ID = 147
SERIE_B_ID = 72

st.title("🧑‍🤝‍🧑 Elenco & Jogadores — Profissional")

# ---------------------------------
# Filtros globais
# ---------------------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
only_pro = st.sidebar.toggle("Somente elenco profissional ativo (Série B)", value=True)
page = st.sidebar.number_input("Página (API)", min_value=1, value=1, step=1)

# Header com logos
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    title_suffix = " (Profissional)" if only_pro else ""
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}{title_suffix}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("Dados vindos de /players. Quando o filtro de **profissional** está ligado, mostramos apenas quem atuou/está inscrito pelo Coritiba na Série B.")

# ---------------------------------
# Funções auxiliares de filtro
# ---------------------------------
def pick_professional_stats(stats_list):
    """
    Escolhe do vetor statistics[] somente a entrada:
    - da Série B (league.id = 72) OU league.name contém 'Serie B'
    - do Coritiba (team.id = 147) OU team.name = 'Coritiba'
    - com minutos > 0 OU aparições > 0
    Retorna o dicionário stats válido ou None.
    """
    if not stats_list:
        return None
    for s in stats_list:
        league = s.get("league", {}) or {}
        team_ = s.get("team", {}) or {}
        games = s.get("games", {}) or {}

        league_ok = (league.get("id") == SERIE_B_ID) or ("serie b" in str(league.get("name","")).lower())
        team_ok = (team_.get("id") == CORITIBA_ID) or (str(team_.get("name","")).lower() == "coritiba")
        minutes = games.get("minutes") or 0
        apps = games.get("appearences") or 0
        contributed = (minutes > 0) or (apps > 0)

        if league_ok and team_ok and contributed:
            return s
    return None

# ---------------------------------
# Busca bruta (paginada) e filtragem
# ---------------------------------
raw = api_client.api_get("players", {"team": team["team_id"], "season": season, "page": page})
if not raw:
    st.warning("Sem dados de jogadores para esta temporada/página.")
    st.stop()

rows = []
for item in raw:
    player = item.get("player", {}) or {}
    stats_list = item.get("statistics") or []

    # Quando only_pro=True, filtra por Série B + Coritiba + minutos/aparições
    if only_pro:
        s = pick_professional_stats(stats_list)
        if not s:
            continue
    else:
        # Sem filtro: usa a primeira estatística disponível (se houver)
        s = (stats_list[0] if stats_list else {}) or {}

    games = s.get("games", {}) or {}
    goals = s.get("goals", {}) or {}
    shots = s.get("shots", {}) or {}
    passes = s.get("passes", {}) or {}
    duels = s.get("duels", {}) or {}
    cards = s.get("cards", {}) or {}

    minutes = games.get("minutes") or 0
    played = games.get("appearences") or 0
    position = games.get("position") or "-"
    rating = games.get("rating")
    try:
        rating = float(rating) if rating else None
    except Exception:
        rating = None

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
    if only_pro:
        st.info("Nenhum atleta do elenco profissional do Coritiba com minutos/aparições na Série B nessa temporada/página.")
    else:
        st.info("Nenhum atleta retornado para esta página.")
    st.stop()

# ---------------------------------
# Filtros de UI (posição + ordenação)
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
# Render dos cards de jogadores
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

st.caption("Fonte: API-Football — /players (filtrado por time=147; quando ativo, liga=72 e minutos/aparições > 0).")
