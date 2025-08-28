import math
from itertools import product

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from core import api_client, ui_utils, ai

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
CORITIBA_ID = 147    # fixo
SERIE_B_ID = 72      # fixo


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _is_final(fx) -> bool:
    return (fx["fixture"].get("status", {}).get("short") or "") in {"FT", "AET", "PEN"}


def _stat_value(items, keys):
    """Busca valor numérico tentando várias chaves (normaliza %)."""
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


def poisson_pmf(lmbda, k):
    """P(k; λ) = e^-λ * λ^k / k!"""
    if lmbda is None or lmbda < 0:
        return 0.0
    try:
        return math.exp(-lmbda) * (lmbda ** k) / math.factorial(k)
    except Exception:
        return 0.0


def score_matrix(lambda_for, lambda_against, max_g=4):
    """Matriz de probabilidade de placar (0..max_g) x (0..max_g)."""
    rows = []
    for g_for in range(0, max_g + 1):
        for g_against in range(0, max_g + 1):
            p = poisson_pmf(lambda_for, g_for) * poisson_pmf(lambda_against, g_against)
            rows.append({"GF": g_for, "GA": g_against, "Prob": p})
    df = pd.DataFrame(rows)
    # normaliza (caso truncado em max_g)
    df["Prob"] = df["Prob"] / df["Prob"].sum()
    return df.pivot(index="GF", columns="GA", values="Prob")


# ------------------------------------------------------------
# UI — filtros
# ------------------------------------------------------------
st.title("📊 Desempenho do Time — Série B")

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
janela_rolling = st.sidebar.slider("Janela de série móvel (jogos)", 3, 15, 7, 1)
usar_resumo_ia = st.sidebar.toggle("Mostrar resumo IA", value=False)

team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(CORITIBA_ID, season, "Brazil")

# Header
c1, c2, c3 = st.columns([1, 4, 1])
with c1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with c2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with c3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("KPIs agregados da temporada na Série B, séries móveis, splits casa/fora e previsão de gols (Poisson) para o próximo jogo.")

# ------------------------------------------------------------
# Coleta dados API
# ------------------------------------------------------------
stats = api_client.team_statistics(league["league_id"], season, CORITIBA_ID)
stats = stats[0] if isinstance(stats, list) and stats else stats

fixtures_all = api_client.fixtures(CORITIBA_ID, season) or []
for m in fixtures_all:
    m["_date"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
fixtures_all = sorted(fixtures_all, key=lambda x: x.get("_date") or pd.Timestamp(0))

fixtures_final = [f for f in fixtures_all if _is_final(f)]

# ------------------------------------------------------------
# KPIs básicos + fallback computado
# ------------------------------------------------------------
kpi_cols = st.columns(4)

if stats:
    try:
        shots_avg = (stats["shots"]["for"]["total"] or 0) / max(stats["fixtures"]["played"]["total"] or 1, 1)
    except Exception:
        shots_avg = None
    poss_avg = stats.get("lineups")  # às vezes posse não vem em team_statistics
else:
    shots_avg = None

# Fallback manual a partir das partidas (média por jogo)
shots_sum = []
passes_acc = []
clean_sheets = 0

for fx in fixtures_final:
    our_home = fx["teams"]["home"]["id"] == CORITIBA_ID
    gh, ga = fx["goals"]["home"], fx["goals"]["away"]
    if (gh == 0 and our_home) or (ga == 0 and not our_home):
        clean_sheets += 1

    try:
        blocks = api_client.fixture_statistics(fx["fixture"]["id"])
    except Exception:
        blocks = []

    mine = None
    for b in (blocks or []):
        tid = (b.get("team") or {}).get("id")
        if tid == CORITIBA_ID:
            mine = b
            break
    items = (mine or {}).get("statistics") or []
    shots = _stat_value(items, ["Total Shots", "Shots Total", "Shots"])
    poss = _stat_value(items, ["Ball Possession", "Possession"])
    pass_acc = _stat_value(items, ["Passes %", "Pass Accuracy", "Passes accurate %"])

    if shots is not None:
        shots_sum.append(shots)
    if pass_acc is not None:
        passes_acc.append(pass_acc)

shots_avg = round(np.mean(shots_sum), 2) if shots_sum else (shots_avg if shots_avg else 0)
poss_avg = round(np.mean(passes_acc), 1) if passes_acc else None  # usando % de passes como proxy de posse, se não houver

kpi_cols[0].metric("Média de Chutes/Jogo", shots_avg if shots_avg is not None else 0)
kpi_cols[1].metric("Posse Média (%)", poss_avg if poss_avg is not None else "—")
kpi_cols[2].metric("Passes certos %", round(np.mean(passes_acc), 1) if passes_acc else "—")
kpi_cols[3].metric("Clean Sheets", clean_sheets)

st.divider()

# ------------------------------------------------------------
# Gols por faixa de minuto (já conhecido)
# ------------------------------------------------------------
st.markdown("### ⏱️ Gols por faixa de minuto")

gf_bins = []
ga_bins = []
for fx in fixtures_final:
    fid = fx["fixture"]["id"]
    try:
        events = api_client.fixture_events(fid)
    except Exception:
        events = []

    for ev in (events or []):
        if ev.get("type") != "Goal":
            continue
        minute = (ev.get("time") or {}).get("elapsed") or 0
        # bucket de 15 em 15
        bucket = f"{(minute // 15) * 15:02d}-{((minute // 15) * 15 + 14):02d}"
        tid = (ev.get("team") or {}).get("id")
        if tid == CORITIBA_ID:
            gf_bins.append(bucket)
        else:
            ga_bins.append(bucket)

def _to_df(bins):
    return pd.Series(bins).value_counts().sort_index().rename_axis("minuto").reset_index(name="total") if bins else pd.DataFrame({"minuto": [], "total": []})

df_gf = _to_df(gf_bins)
df_ga = _to_df(ga_bins)

c1, c2 = st.columns(2)
with c1:
    st.subheader("⚽ Gols Pró por faixa de minuto")
    if df_gf.empty:
        st.info("Sem eventos de gol do Coritiba registrados.")
    else:
        st.plotly_chart(px.bar(df_gf, x="minuto", y="total"), use_container_width=True)
with c2:
    st.subheader("🧱 Gols Contra por faixa de minuto")
    if df_ga.empty:
        st.info("Sem eventos de gol contra registrados.")
    else:
        st.plotly_chart(px.bar(df_ga, x="minuto", y="total"), use_container_width=True)

st.caption("Fonte: API-Football — eventos e estatísticas por partida.")

st.divider()

# ------------------------------------------------------------
# Séries móveis: GF/GA, SOT, Corners
# ------------------------------------------------------------
st.markdown("### 📉 Séries móveis (últimos jogos)")

rows_series = []
for fx in fixtures_final:
    f = fx["fixture"]
    home = fx["teams"]["home"]; away = fx["teams"]["away"]
    our_home = (home["id"] == CORITIBA_ID)
    gf = fx["goals"]["home"] if our_home else fx["goals"]["away"]
    ga = fx["goals"]["away"] if our_home else fx["goals"]["home"]

    try:
        blocks = api_client.fixture_statistics(f["id"])
    except Exception:
        blocks = []
    my_items, opp_items = [], []
    for b in (blocks or []):
        tid = (b.get("team") or {}).get("id")
        if tid == CORITIBA_ID:
            my_items = b.get("statistics") or []
        else:
            opp_items = b.get("statistics") or []

    sot = _stat_value(my_items, ["Shots on Goal", "Shots on Target", "SOT"])
    corners_for = _stat_value(my_items, ["Corner Kicks", "Corners"])
    corners_against = _stat_value(opp_items, ["Corner Kicks", "Corners"])

    rows_series.append({
        "date": pd.to_datetime(f["date"], errors="coerce"),
        "GF": gf, "GA": ga, "SOT": sot,
        "Corners_for": corners_for, "Corners_against": corners_against,
        "H/A": "H" if our_home else "A"
    })

df_s = pd.DataFrame(rows_series).sort_values("date").reset_index(drop=True)

def roll_mean(series, w):
    s = pd.to_numeric(series, errors="coerce").rolling(w, min_periods=1).mean()
    return s

plots = [
    ("GF", "Gols Pró"),
    ("GA", "Gols Contra"),
    ("SOT", "Chutes no alvo"),
    ("Corners_for", "Escanteios a favor"),
    ("Corners_against", "Escanteios contra")
]

for key, label in plots:
    if key not in df_s or df_s[key].dropna().empty:
        continue
    df_plot = df_s[["date", key]].copy()
    df_plot["Média móvel"] = roll_mean(df_plot[key], janela_rolling)
    df_plot = df_plot.rename(columns={key: "Valor"})

    m = df_plot.melt(id_vars="date", var_name="Série", value_name="Valor")
    fig = px.line(m, x="date", y="Valor", color="Série", title=label)
    fig.update_layout(xaxis_title="Data", yaxis_title=label)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ------------------------------------------------------------
# Split Casa x Fora — PPG, GF/GA por jogo e resultados
# ------------------------------------------------------------
st.markdown("### 🏟️ Casa x Fora")

if df_s.empty:
    st.info("Sem partidas finalizadas para compor os splits.")
else:
    df_s["points"] = 0
    for i, fx in enumerate(fixtures_final):
        f = fx["fixture"]; home = fx["teams"]["home"]; away = fx["teams"]["away"]
        our_home = (home["id"] == CORITIBA_ID)
        gh, ga = fx["goals"]["home"], fx["goals"]["away"]
        res_points = 3 if ((our_home and gh > ga) or ((not our_home) and ga > gh)) else (1 if gh == ga else 0)
        df_s.loc[i, "points"] = res_points

    grp = df_s.groupby("H/A").agg(
        jogos=("H/A", "count"),
        ppg=("points", "mean"),
        gfpg=("GF", "mean"),
        gapg=("GA", "mean")
    ).reset_index()

    st.dataframe(grp, use_container_width=True, hide_index=True)
    st.plotly_chart(px.bar(grp, x="H/A", y=["ppg", "gfpg", "gapg"], barmode="group"), use_container_width=True)

st.divider()

# ------------------------------------------------------------
# Previsão de gols (Poisson) — próximo jogo
# ------------------------------------------------------------
st.markdown("### 🔮 Previsão de gols — próximo jogo (modelo Poisson simples)")

next_fx = api_client.fixtures(CORITIBA_ID, season, next=1)
if not next_fx:
    st.info("Nenhum próximo jogo encontrado.")
else:
    fx = next_fx[0]
    home = fx["teams"]["home"]; away = fx["teams"]["away"]
    is_home = home["id"] == CORITIBA_ID
    opp = away if is_home else home

    # λ estimados: médias recentes (últimos N finalizados)
    N = max(6, janela_rolling)  # usa pelo menos 6 jogos
    df_recent = df_s.tail(N)

    lambda_for = df_recent["GF"].dropna().mean() if not df_recent.empty else None
    lambda_against = df_recent["GA"].dropna().mean() if not df_recent.empty else None

    # Ajuste simples por fator casa/fora: +10% em casa, -10% fora
    if lambda_for is not None:
        lambda_for = float(lambda_for) * (1.10 if is_home else 0.90)
    if lambda_against is not None:
        lambda_against = float(lambda_against) * (0.90 if is_home else 1.10)

    cl, cm, cr = st.columns([2, 3, 2])
    with cl:
        st.markdown(f"**Próximo adversário:** {opp['name']}")
        st.caption(f"Local: {'Casa' if is_home else 'Fora'}")
        st.caption(f"λ gols CFC: **{lambda_for:.2f}**  •  λ gols contra: **{lambda_against:.2f}**" if (lambda_for and lambda_against) else "Sem base suficiente para estimar λ.")

    if lambda_for and lambda_against:
        mat = score_matrix(lambda_for, lambda_against, max_g=4)
        heat = px.imshow(mat.values, x=mat.columns, y=mat.index, aspect="auto", origin="lower",
                         labels=dict(x="Gols Sofridos", y="Gols Marcados", color="Prob"))
        heat.update_layout(title="Probabilidade de placar (0–4)", xaxis_nticks=len(mat.columns), yaxis_nticks=len(mat.index))
        with cm:
            st.plotly_chart(heat, use_container_width=True)

        # Placar mais provável e prob. de vitória/empate/derrota
        flat = mat.stack().reset_index()
        flat.columns = ["GF", "GA", "Prob"]
        best = flat.loc[flat["Prob"].idxmax()]
        pw = float(flat[flat["GF"] > flat["GA"]]["Prob"].sum())
        pd = float(flat[flat["GF"] == flat["GA"]]["Prob"].sum())
        pl = float(flat[flat["GF"] < flat["GA"]]["Prob"].sum())

        with cr:
            st.metric("Placar mais provável", f"{int(best['GF'])} x {int(best['GA'])}")
            st.write(f"Vitória: **{pw:.0%}**")
            st.write(f"Empate: **{pd:.0%}**")
            st.write(f"Derrota: **{pl:.0%}**")
    else:
        st.info("Não foi possível calcular a matriz de probabilidades (falta de jogos recentes com gols).")

st.divider()

# ------------------------------------------------------------
# Resumo IA (opcional)
# ------------------------------------------------------------
if usar_resumo_ia:
    st.markdown("### 🤖 Resumo IA (experimental)")
    ctx = {
        "season": season,
        "team": team,
        "league": league,
        "kpis": {
            "shots_avg": shots_avg,
            "possession_avg": poss_avg,
            "clean_sheets": clean_sheets,
        },
        "recent_form": df_s.tail(6).to_dict(orient="records")
    }
    try:
        with st.spinner("Gerando resumo…"):
            cards = ai.generate_insights({"mode": "team_performance", **ctx}) or []
        for ins in cards:
            with st.container(border=True):
                st.subheader(ins.get("title", "Resumo"))
                st.write(ins.get("summary", ""))
    except Exception:
        st.info("Não foi possível gerar o resumo IA agora.")
