import streamlit as st
import pandas as pd
from core import api_client, ui_utils

st.title("🩺 Diagnóstico de Dados — Cobertura por Partida")

# Filtros básicos
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
max_games = st.sidebar.slider("Limitar a N jogos (mais recentes)", 10, 100, 40, 5)
show_only_missing = st.sidebar.toggle("Mostrar somente jogos com dados faltantes", value=False)

# Cabeçalho com logos
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")
h1, h2, h3 = st.columns([1,4,1])
with h1:
    ui_utils.load_image(team["team_logo"], size=48, alt="Logo Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=48, alt="Logo Liga")

st.caption("Tabela para inspecionar quais métricas chegam por jogo (e onde há lacunas). Útil para depurar páginas com dados antigos.")

# ----------------------------
# Helpers
# ----------------------------
OUR_ID = team["team_id"]

def _stat_value(items, keys):
    """Busca o valor numérico de uma estatística tentando várias chaves comuns."""
    for k in keys:
        for it in items:
            if (it.get("type") or "").lower() == k.lower():
                v = it.get("value")
                if v is None:
                    return None
                if isinstance(v, str) and "%" in v:
                    try:
                        return float(v.replace("%", "").strip())
                    except Exception:
                        return None
                try:
                    return float(v)
                except Exception:
                    try:
                        return int(v)
                    except Exception:
                        return None
    return None

# ----------------------------
# Coleta fixtures
# ----------------------------
fixtures = api_client.fixtures(OUR_ID, season)
if not fixtures:
    st.warning("Nenhuma partida retornada para esta temporada.")
    st.stop()

# Ordena por data desc e limita
for m in fixtures:
    m["_d"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
fixtures = sorted(fixtures, key=lambda x: x.get("_d") or pd.Timestamp(0), reverse=True)[:max_games]

rows = []
progress = st.progress(0)
total = len(fixtures)

for i, fx in enumerate(fixtures, start=1):
    progress.progress(i/total)

    f = fx["fixture"]
    h = fx["teams"]["home"]; a = fx["teams"]["away"]
    home_game = (h["id"] == OUR_ID)
    opp = a if home_game else h

    gf = fx["goals"]["home"] if home_game else fx["goals"]["away"]
    ga = fx["goals"]["away"] if home_game else fx["goals"]["home"]
    score = None if (gf is None or ga is None) else f"{int(gf)}-{int(ga)}"

    # Estatísticas do fixture
    try:
        blocks = api_client.fixture_statistics(f["id"])
    except Exception:
        blocks = []

    my_items, opp_items = [], []
    for b in (blocks or []):
        tid = (b.get("team") or {}).get("id")
        if tid == OUR_ID:
            my_items = b.get("statistics") or []
        else:
            opp_items = b.get("statistics") or []

    # Extrai métricas principais (as mesmas usadas no dashboard)
    metric_map = {
        "Shots": ["Total Shots", "Shots Total", "Shots"],
        "SOT": ["Shots on Goal", "Shots on Target", "SOT"],
        "Poss%": ["Ball Possession", "Possession"],
        "Corners_for": ["Corner Kicks", "Corners"],
        "Fouls_for": ["Fouls"],
        "YC_for": ["Yellow Cards"],
        "RC_for": ["Red Cards"],
    }
    metric_map_opp = {
        "Corners_against": ["Corner Kicks", "Corners"],
        "Fouls_against": ["Fouls"],
        "YC_against": ["Yellow Cards"],
        "RC_against": ["Red Cards"],
    }

    shots = _stat_value(my_items, metric_map["Shots"])
    sot = _stat_value(my_items, metric_map["SOT"])
    poss = _stat_value(my_items, metric_map["Poss%"])
    corners_for = _stat_value(my_items, metric_map["Corners_for"])
    fouls_for = _stat_value(my_items, metric_map["Fouls_for"])
    yc_for = _stat_value(my_items, metric_map["YC_for"])
    rc_for = _stat_value(my_items, metric_map["RC_for"])

    corners_against = _stat_value(opp_items, metric_map_opp["Corners_against"])
    fouls_against = _stat_value(opp_items, metric_map_opp["Fouls_against"])
    yc_against = _stat_value(opp_items, metric_map_opp["YC_against"])
    rc_against = _stat_value(opp_items, metric_map_opp["RC_against"])

    # Eventos (para verificar cartões quando stats vierem vazias)
    try:
        events = api_client.fixture_events(f["id"])
    except Exception:
        events = []

    have_stats = bool(my_items or opp_items)
    have_events = bool(events)

    # Lista campos faltantes
    missing = []
    for k, v in {
        "Shots": shots, "SOT": sot, "Poss%": poss,
        "Corners_for": corners_for, "Corners_against": corners_against,
        "Fouls_for": fouls_for, "Fouls_against": fouls_against,
        "YC_for": yc_for, "RC_for": rc_for, "YC_against": yc_against, "RC_against": rc_against
    }.items():
        if v is None:
            missing.append(k)

    rows.append({
        "date": str(f["date"])[:19],
        "fixture_id": f["id"],
        "H/A": "H" if home_game else "A",
        "opponent": opp["name"],
        "score": score or f.get("status", {}).get("short", "-"),
        "have_stats": have_stats,
        "have_events": have_events,
        "Shots": shots,
        "SOT": sot,
        "Poss%": poss,
        "Corners_for": corners_for,
        "Corners_against": corners_against,
        "Fouls_for": fouls_for,
        "Fouls_against": fouls_against,
        "YC_for": yc_for,
        "RC_for": rc_for,
        "YC_against": yc_against,
        "RC_against": rc_against,
        "missing_fields": ", ".join(missing) if missing else "",
    })

progress.empty()

df = pd.DataFrame(rows)

# Filtro "somente com faltas"
if show_only_missing:
    df_view = df[df["missing_fields"] != ""].copy()
else:
    df_view = df.copy()

# Ordena e mostra
df_view = df_view.sort_values("date", ascending=False).reset_index(drop=True)

st.dataframe(
    df_view,
    use_container_width=True,
    hide_index=True,
    column_config={
        "have_stats": st.column_config.CheckboxColumn("stats?"),
        "have_events": st.column_config.CheckboxColumn("events?"),
    }
)

# Resumo
st.markdown("### Resumo")
total_jogos = len(df)
com_stats = int(df["have_stats"].sum())
com_events = int(df["have_events"].sum())
faltantes = int((df["missing_fields"] != "").sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total de jogos", total_jogos)
c2.metric("Com estatísticas", com_stats)
c3.metric("Com eventos", com_events)
c4.metric("Com campos faltantes", faltantes)

# Exportação
st.markdown("### Exportar CSV")
csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Baixar diagnóstico (CSV)",
    data=csv,
    file_name=f"diagnostico_cobertura_{season}.csv",
    mime="text/csv"
)

st.caption("Fonte: API-Football — /fixtures, /fixtures/statistics, /fixtures/events. Jogos antigos podem não possuir cobertura completa da API.")
