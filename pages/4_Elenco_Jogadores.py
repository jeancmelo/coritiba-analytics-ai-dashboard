import streamlit as st
import pandas as pd
from core import api_client, ui_utils
from core.cache import render_cache_controls
render_cache_controls()  # mostra: última atualização + botões

st.title("🧑‍🤝‍🧑 Elenco & Jogadores — Profissional (Série B)")

# filtros globais
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

# header com logos
h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']} (Profissional)")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("Mostrando apenas atletas com **minutos > 0** na **Série B (72)** pelo **Coritiba (147)** nesta temporada.")

CORITIBA_ID = 147
SERIE_B_ID = 72

def pick_professional_stats(stats_list):
    """
    Escolhe do vetor statistics[] somente a entrada:
    - da Série B (league.id = 72)
    - do Coritiba (team.id = 147)
    - com minutos > 0 (atuou)
    Retorna o dicionário stats válido ou None.
    """
    if not stats_list:
        return None
    for s in stats_list:
        league_ok = (s.get("league", {}) or {}).get("id") == SERIE_B_ID
        team_ok = (s.get("team", {}) or {}).get("id") == CORITIBA_ID
        games = s.get("games", {}) or {}
        minutes = games.get("minutes") or 0
        if league_ok and team_ok and minutes and minutes > 0:
            return s
    return None

# ---------------------------
# Coleta todas as páginas
# ---------------------------
with st.spinner("Carregando jogadores…"):
    page = 1
    rows = []
    max_pages = 20  # segurança
    fetched = 0
    while page <= max_pages:
        chunk = api_client.api_get("players", {"team": team["team_id"], "season": season, "page": page}) or []
        if not chunk:
            break
        fetched += len(chunk)
        for item in chunk:
            player = item.get("player", {}) or {}
            s = pick_professional_stats(item.get("statistics") or [])
            if not s:
                continue  # ignora quem não atuou na Série B pelo Coritiba

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
            rows.append({
                "foto": player.get("photo"),
                "nome": player.get("name"),
                "idade": player.get("age"),
                "pos": position,
                "min": minutes,
                "jogos": played,
                "gols": g_total,
                "assist": a_total,
                "g90": round(g_total / per90, 2) if per90 else 0,
                "a90": round(a_total / per90, 2) if per90 else 0,
                "sot": sot,
                "sot90": round(sot / per90, 2) if per90 else 0,
                "keyP": key_passes,
                "kp90": round(key_passes / per90, 2) if per90 else 0,
                "duels%": round((duels_won / duels_total * 100), 1) if duels_total else None,
                "YC": yc,
                "RC": rc,
                "rating": rating,
            })
        page += 1

df = pd.DataFrame(rows)

if df.empty:
    st.info("Nenhum atleta com minutos na Série B para essa temporada.")
    st.stop()

# filtros de UI
posicoes = ["Todos"] + sorted([p for p in df["pos"].dropna().unique() if p])
pos_sel = st.selectbox("Filtrar por posição", posicoes, index=0)

if pos_sel != "Todos":
    df_view = df[df["pos"] == pos_sel].copy()
else:
    df_view = df.copy()

ordens = {
    "Minutos": "min",
    "Rating": "rating",
    "Gols": "gols",
    "Assistências": "assist",
    "Gols/90": "g90",
    "Assist./90": "a90",
    "SOT/90": "sot90",
    "Key passes/90": "kp90",
}
ordem_sel = st.selectbox("Ordenar por", list(ordens.keys()), index=0)
asc = st.toggle("Ordem crescente?", value=False)

df_view = df_view.sort_values(ordens[ordem_sel], ascending=asc, na_position="last")

st.divider()

# render cards de jogadores (todos de uma vez)
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
        m1.metric("Min", int(r["min"]))
        m2.metric("Gols", int(r["gols"]))
        m3.metric("Assist.", int(r["assist"]))

        m4, m5, m6 = st.columns(3)
        m4.metric("G/90", r["g90"])
        m5.metric("A/90", r["a90"])
        m6.metric("SOT/90", r["sot90"])

        m7, m8, m9 = st.columns(3)
        m7.metric("KeyP/90", r["kp90"])
        m8.metric("Duelos %", r["duels%"] if pd.notna(r["duels%"]) else 0)
        m9.metric("Cartões", f"{int(r['YC'])}🟨 / {int(r['RC'])}🟥")

    st.markdown("---")

st.caption("Fonte: API-Football — /players (todas as páginas), filtrado por liga=72, time=147 e minutos > 0.")
