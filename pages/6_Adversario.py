# pages/6_Adversario.py
import math
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

from core import api_client, ui_utils, ai
from core.cache import render_cache_controls, get_json

render_cache_controls()

st.title("🔎 Scouting do Adversário — Prévia do próximo jogo")

# ---------------------------------------------------------------------
# Constantes (IDs fixos) + filtros
# ---------------------------------------------------------------------
CORITIBA_ID = 147
SERIE_B_ID  = 72

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

team   = api_client.team_by_id(CORITIBA_ID)
league = api_client.league_by_id(SERIE_B_ID)

h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team.get("team_logo"), size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team.get('team_name','Coritiba')} — {season} • {league.get('league_name','Série B')}")
with h3:
    ui_utils.load_image(league.get("league_logo"), size=56, alt="Logo da Liga")

st.caption("Análise do próximo adversário com estatísticas recentes, head-to-head, probabilidades e prévia com IA.")

OUR_ID = CORITIBA_ID
FINALS = {"FT", "AET", "PEN"}

def _is_final(fx) -> bool:
    try:
        return ((fx.get("fixture") or {}).get("status") or {}).get("short") in FINALS
    except Exception:
        return False

def _fmt_score(gf, ga):
    if gf is None or ga is None:
        return "-"
    return f"{int(gf)}–{int(ga)}"

def _safe_pct(s):
    if s is None:
        return None
    if isinstance(s, str) and "%" in s:
        try:
            return float(s.replace("%", "").strip())
        except Exception:
            return None
    try:
        return float(s)
    except Exception:
        return None

def _avg(lst):
    vals = [_safe_pct(x) for x in lst if x is not None]
    return round(float(np.mean(vals)), 2) if vals else None

# ---------------------------------------------------------------------
# 1) Próximo adversário
# ---------------------------------------------------------------------
next_fx = api_client.fixtures(OUR_ID, season, next=1)
if not next_fx:
    st.info("Nenhum próximo jogo encontrado na API.")
    st.stop()

fx = next_fx[0]
home = (fx.get("teams") or {}).get("home", {})
away = (fx.get("teams") or {}).get("away", {})
is_home = (home.get("id") == OUR_ID)
opp = away if is_home else home
opp_id = opp.get("id")

c1, c2 = st.columns([1, 8])
with c1:
    ui_utils.load_image(opp.get("logo"), size=56, alt=opp.get("name"))
with c2:
    st.subheader(f"🆚 Próximo adversário: {opp.get('name')}")
    try:
        dt = pd.to_datetime((fx.get("fixture") or {}).get("date"))
        st.caption(f"Data: {dt.strftime('%d/%m/%Y %H:%M')} • Rodada: {(fx.get('league') or {}).get('round')}")
    except Exception:
        st.caption(f"Rodada: {(fx.get('league') or {}).get('round')}")

st.markdown("---")

# ---------------------------------------------------------------------
# 2) Forma recente do adversário (últimos 5 finalizados)
# ---------------------------------------------------------------------
st.markdown("### 📈 Forma recente (últimos 5 jogos)")
st.caption("**O que é**: últimos 5 jogos finalizados do adversário na temporada corrente (placar e resultado do ponto de vista do adversário).")

opp_fixtures_all = api_client.fixtures(opp_id, season) or []
for m in opp_fixtures_all:
    m["_d"] = pd.to_datetime((m.get("fixture") or {}).get("date"), errors="coerce")
opp_finals = [m for m in sorted(opp_fixtures_all, key=lambda x: x.get("_d") or pd.Timestamp(0), reverse=True) if _is_final(m)]
opp_last5 = opp_finals[:5]

rows = []
for it in opp_last5:
    f = it.get("fixture") or {}
    t = it.get("teams") or {}
    h, a = t.get("home", {}), t.get("away", {})
    opp_home = (h.get("id") == opp_id)
    gh = (it.get("goals") or {}).get("home")
    ga = (it.get("goals") or {}).get("away")
    gf = gh if opp_home else ga
    ga_ = ga if opp_home else gh
    res = "-"
    if gf is not None and ga_ is not None:
        res = "V" if gf > ga_ else ("D" if gf < ga_ else "E")
    rows.append({
        "Data": str(f.get("date"))[:10],
        "Adversário": (a.get("name") if opp_home else h.get("name")),
        "Placar": _fmt_score(gf, ga_),
        "Res": res
    })

df_last5 = pd.DataFrame(rows)
st.dataframe(df_last5, use_container_width=True, hide_index=True)

st.markdown("---")

# ---------------------------------------------------------------------
# 3) KPIs do adversário (médias por jogo)
# ---------------------------------------------------------------------
st.markdown("### 🔢 KPIs principais do adversário (Série B)")
st.caption("**O que é**: médias por jogo (GF, GA, SOT, posse, passes certos, escanteios) com base em jogos finalizados desta temporada.")

opp_stats = api_client.team_statistics(SERIE_B_ID, season, opp_id) or {}
if isinstance(opp_stats, list):
    opp_stats = opp_stats[0] if opp_stats else {}

take_n = min(10, len(opp_finals))
shots, sots, poss, pass_acc, corners_for, corners_against = [], [], [], [], [], []
for it in opp_finals[:take_n]:
    try:
        blocks = api_client.fixture_statistics((it.get("fixture") or {}).get("id")) or []
    except Exception:
        blocks = []
    my_items, opp_items = [], []
    for b in blocks:
        tid = (b.get("team") or {}).get("id")
        if tid == opp_id:
            my_items = b.get("statistics") or []
        else:
            opp_items = b.get("statistics") or []

    def pick(items, aliases):
        aliases_l = [a.lower() for a in aliases]
        for x in (items or []):
            t = (x.get("type") or "").lower()
            if t in aliases_l:
                return x.get("value")
        for x in (items or []):
            t = (x.get("type") or "").lower()
            if any(t.startswith(a) for a in aliases_l):
                return x.get("value")
        return None

    shots.append(_safe_pct(pick(my_items, ["total shots", "shots total", "shots"])))
    sots.append(_safe_pct(pick(my_items, ["shots on goal", "shots on target", "sot"])))
    poss.append(_safe_pct(pick(my_items, ["ball possession", "possession"])))
    # qualquer métrica de % de passe
    pass_acc.append(_safe_pct(next((x.get("value") for x in (my_items or []) if "pass" in (x.get("type") or "").lower() and "%" in str(x.get("value"))), None)))
    corners_for.append(_safe_pct(pick(my_items, ["corner kicks", "corners"])))
    corners_against.append(_safe_pct(pick(opp_items, ["corner kicks", "corners"])))

def goals_avg(block, side):
    try:
        val = (((block.get("goals") or {}).get(side) or {}).get("average") or {}).get("total")
        return float(val) if val is not None else None
    except Exception:
        return None

gf_avg = goals_avg(opp_stats, "for")
ga_avg = goals_avg(opp_stats, "against")

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Gols Pró/jogo",       "—" if gf_avg is None else round(gf_avg, 2))
k2.metric("Gols Contra/jogo",    "—" if ga_avg is None else round(ga_avg, 2))
k3.metric("SOT/jogo",            "—" if _avg(sots) is None else _avg(sots))
k4.metric("Posse (%)",           "—" if _avg(poss) is None else _avg(poss))
k5.metric("Passes certos (%)",   "—" if _avg(pass_acc) is None else _avg(pass_acc))
k6.metric("Escanteios/jogo",     "—" if _avg(corners_for) is None else _avg(corners_for))

st.markdown("---")

# ---------------------------------------------------------------------
# 4) Forças & Fragilidades (heurísticas simples)
# ---------------------------------------------------------------------
st.markdown("### 🧭 Forças & Fragilidades (heurísticas)")

def minute_bucket(block, side, rng):
    try:
        return (((block.get("goals") or {}).get(side) or {}).get("minute") or {}).get(rng, {}).get("total")
    except Exception:
        return None

bullets_str, bullets_weak = [], []
m_fin = _safe_pct(minute_bucket(opp_stats, "for", "76-90"))
if m_fin and m_fin >= 4:
    bullets_str.append("Marca frequentemente entre **76–90'**.")
s_fin = _safe_pct(minute_bucket(opp_stats, "against", "76-90"))
if s_fin and s_fin >= 4:
    bullets_weak.append("Costuma **sofrer gols no fim (76–90')**.")
if gf_avg and gf_avg >= 1.5:
    bullets_str.append("**Ataque acima da média** (GF/jogo ≥ 1.5).")
if ga_avg and ga_avg >= 1.5:
    bullets_weak.append("**Defesa vulnerável** (GA/jogo ≥ 1.5).")

if not bullets_str and not bullets_weak:
    st.caption("Sem sinais fortes com as heurísticas atuais.")
else:
    if bullets_str:
        st.markdown("**Forças**")
        for b in bullets_str:
            st.markdown(f"- {b}")
    if bullets_weak:
        st.markdown("**Fragilidades**")
        for b in bullets_weak:
            st.markdown(f"- {b}")

st.markdown("---")

# ---------------------------------------------------------------------
# 5) Head-to-Head (H2H) — corrigido
# ---------------------------------------------------------------------
st.markdown("### 🤝 Confrontos diretos (H2H)")
st.caption("**O que é**: últimos confrontos entre Coritiba e o adversário na base da API.")

# 👉 usa get_json direto (api_client.api_get não existe para esse endpoint)
h2h_payload = get_json("/fixtures/headtohead", {"h2h": f"{OUR_ID}-{opp_id}", "last": 10}) or {}
h2h = h2h_payload.get("response") or []

for m in h2h:
    try:
        m["_d"] = pd.to_datetime((m.get("fixture") or {}).get("date"))
    except Exception:
        m["_d"] = pd.NaT
h2h = sorted(h2h, key=lambda x: x.get("_d") or pd.Timestamp(0), reverse=True)

rows_h2h, w, d, l = [], 0, 0, 0
for it in h2h[:10]:
    f = it.get("fixture") or {}
    t = it.get("teams") or {}
    h, a = t.get("home", {}), t.get("away", {})
    our_home = (h.get("id") == OUR_ID)
    gh = (it.get("goals") or {}).get("home")
    ga = (it.get("goals") or {}).get("away")
    gf = gh if our_home else ga
    ga_ = ga if our_home else gh

    res = "-"
    if gf is not None and ga_ is not None:
        if gf > ga_:
            res = "V"; w += 1
        elif gf < ga_:
            res = "D"; l += 1
        else:
            res = "E"; d += 1

    rows_h2h.append({
        "Data": str(f.get("date"))[:10],
        "Coritiba": (h.get("name") if our_home else a.get("name")),
        "Adversário": (a.get("name") if our_home else h.get("name")),
        "Placar": _fmt_score(gf, ga_),
        "Res (Coxa)": res
    })

if rows_h2h:
    st.caption(f"Resumo (últimos {len(rows_h2h)}): **{w}V {d}E {l}D**")
    st.dataframe(pd.DataFrame(rows_h2h), use_container_width=True, hide_index=True)
else:
    st.info("Sem confrontos diretos recentes na base da API.")

st.markdown("---")

# ---------------------------------------------------------------------
# 6) Probabilidades (Poisson) para o confronto
# ---------------------------------------------------------------------
st.markdown("### 🔮 Probabilidade de resultados (Poisson)")
st.caption("**Como funciona**: aproximação de Poisson usando médias de gols do Coxa e do adversário.")

coxa_fixtures = api_client.fixtures(OUR_ID, season) or []
for m in coxa_fixtures:
    m["_d"] = pd.to_datetime((m.get("fixture") or {}).get("date"), errors="coerce")
coxa_finals = [m for m in coxa_fixtures if _is_final(m)]
gf_list, ga_list = [], []
for it in coxa_finals:
    t = it.get("teams") or {}
    h, a = t.get("home", {}), t.get("away", {})
    our_home = (h.get("id") == OUR_ID)
    gh = (it.get("goals") or {}).get("home")
    ga = (it.get("goals") or {}).get("away")
    gf_list.append(gh if our_home else ga)
    ga_list.append(ga if our_home else gh)

coxa_gf = _avg(gf_list) or 1.0
coxa_ga = _avg(ga_list) or 1.0
opp_gf  = ( ((opp_stats.get("goals") or {}).get("for") or {}).get("average") or {} ).get("total")
opp_ga  = ( ((opp_stats.get("goals") or {}).get("against") or {}).get("average") or {} ).get("total")
opp_gf  = float(opp_gf) if opp_gf is not None else 1.0
opp_ga  = float(opp_ga) if opp_ga is not None else 1.0

lam_us   = float(np.mean([coxa_gf, opp_ga]))
lam_them = float(np.mean([coxa_ga, opp_gf]))

def pois_pmf(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

max_goals = 5
grid = np.array([[pois_pmf(i, lam_us) * pois_pmf(j, lam_them)
                  for j in range(max_goals+1)] for i in range(max_goals+1)], dtype=float)
grid = grid / grid.sum()

p_win  = float(np.triu(grid, 1).sum())
p_lose = float(np.tril(grid, -1).sum())
p_draw = float(np.trace(grid))

p_over25 = float(sum(grid[i, j] for i in range(max_goals+1) for j in range(max_goals+1) if i + j >= 3))
p_btts   = float(sum(grid[i, j] for i in range(1, max_goals+1) for j in range(1, max_goals+1)))

cols = st.columns(3)
cols[0].metric("Vitória (Coxa)", f"{round(p_win*100,1)}%")
cols[1].metric("Empate",         f"{round(p_draw*100,1)}%")
cols[2].metric("Derrota",        f"{round(p_lose*100,1)}%")

cols = st.columns(3)
cols[0].metric("Over 2.5",          f"{round(p_over25*100,1)}%")
cols[1].metric("BTTS",              f"{round(p_btts*100,1)}%")
cols[2].metric("xG simples (Coxa)", round(lam_us, 2))

out = []
for i in range(max_goals + 1):
    for j in range(max_goals + 1):
        out.append((i, j, float(grid[i, j])))
top6 = sorted(out, key=lambda x: x[2], reverse=True)[:6]
st.markdown("**Placares mais prováveis**")
st.dataframe(pd.DataFrame([{"Placar": f"{i}–{j}", "Prob%": round(p*100, 2)} for i, j, p in top6]),
             use_container_width=True, hide_index=True)

st.markdown("---")

# ---------------------------------------------------------------------
# 7) Prévia IA do confronto
# ---------------------------------------------------------------------
st.markdown("### 🧠 Prévia IA do confronto")

# contexto Coxa — últimos 10 finalizados
for m in coxa_finals:
    m["_d"] = pd.to_datetime((m.get("fixture") or {}).get("date"), errors="coerce")
coxa_finals = sorted(coxa_finals, key=lambda x: x["_d"] or pd.Timestamp(0), reverse=True)[:10]
ctx_last_coxa = []
for it in coxa_finals:
    t = it.get("teams") or {}
    h, a = t.get("home", {}), t.get("away", {})
    gh = (it.get("goals") or {}).get("home")
    ga = (it.get("goals") or {}).get("away")
    ctx_last_coxa.append({
        "date": str((it.get("fixture") or {}).get("date"))[:19],
        "home": h.get("name"), "away": a.get("name"),
        "score": f"{gh}-{ga}",
        "is_home": (h.get("id") == OUR_ID)
    })

# contexto adversário — últimos 10 finalizados
ctx_last_opp = []
for it in opp_finals[:10]:
    t = it.get("teams") or {}
    h, a = t.get("home", {}), t.get("away", {})
    gh = (it.get("goals") or {}).get("home")
    ga = (it.get("goals") or {}).get("away")
    ctx_last_opp.append({
        "date": str((it.get("fixture") or {}).get("date"))[:19],
        "home": h.get("name"), "away": a.get("name"),
        "score": f"{gh}-{ga}",
        "is_home": (h.get("id") == opp_id)
    })

context = {
    "mode": "pre_match",
    "season": season,
    "league": league,
    "team": team,
    "opponent": {"id": opp_id, "name": opp.get("name"), "logo": opp.get("logo")},
    "match": {
        "fixture_id": (fx.get("fixture") or {}).get("id"),
        "date":        (fx.get("fixture") or {}).get("date"),
        "is_home":     is_home,
        "round":       (fx.get("league") or {}).get("round")
    },
    "team_stats": api_client.team_statistics(SERIE_B_ID, season, OUR_ID),
    "opp_stats":  opp_stats,
    "last_games_team": ctx_last_coxa,
    "last_games_opp":  ctx_last_opp,
    "head_to_head": rows_h2h,
    "simple_poisson": {
        "lambda_team": lam_us,
        "lambda_opp":  lam_them,
        "p_win": p_win, "p_draw": p_draw, "p_lose": p_lose,
        "top_scores": [{"score": f"{i}-{j}", "prob": round(p, 4)} for i, j, p in top6]
    }
}

btn = st.button("Gerar prévia IA")
if btn:
    try:
        with st.spinner("Consultando a IA…"):
            cards = ai.generate_insights(context) or []
        if not cards:
            st.info("A IA não retornou insights para este contexto.")
        else:
            for ins in cards:
                with st.container(border=True):
                    st.caption(ins.get("type", "pre_match"))
                    st.subheader(ins.get("title", "(sem título)"))
                    st.write(ins.get("summary", ""))

                    ev = ins.get("evidence") or []
                    if ev:
                        st.markdown("**Evidências**")
                        for e in ev:
                            lbl = e.get("label", "-"); val = e.get("value", "-")
                            base = e.get("baseline"); unit = e.get("unit", "")
                            base_txt = f" • baseline: {base}" if base is not None else ""
                            st.markdown(f"- **{lbl}**: {val}{unit}{base_txt}")

                    meta = []
                    if ins.get("severity"):   meta.append(f"Severidade: {ins['severity']}")
                    if ins.get("confidence") is not None: meta.append(f"Conf.: {ins['confidence']}")
                    if ins.get("timeframe"): meta.append(f"Janela: {ins['timeframe']}")
                    if meta:
                        st.caption(" • ".join(meta))
    except Exception as e:
        st.error(f"Falha ao gerar a prévia IA: {e}")

st.caption("Fontes: API-Football — /fixtures, /fixtures/statistics, /fixtures/headtohead, /teams/statistics (liga=72).")
