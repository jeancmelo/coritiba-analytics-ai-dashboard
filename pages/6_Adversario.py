import math
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from core import api_client, ui_utils, ai

st.title("🔎 Scouting do Adversário — Prévia do próximo jogo")

# ---------------------------------------------------------------------
# Filtros básicos
# ---------------------------------------------------------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("Análise do próximo adversário com estatísticas recentes, head-to-head, probabilidades e prévia com IA.")

OUR_ID = team["team_id"]
FINALS = {"FT", "AET", "PEN"}

def _is_final(fx) -> bool:
    return (fx["fixture"].get("status", {}).get("short") or "") in FINALS

def _fmt_score(gf, ga):
    if gf is None or ga is None:
        return "-"
    return f"{int(gf)}–{int(ga)}"

def _safe_pct(s):
    if s is None:
        return None
    if isinstance(s, str) and "%" in s:
        try:
            return float(s.replace("%","").strip())
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
home = fx["teams"]["home"]; away = fx["teams"]["away"]
is_home = (home["id"] == OUR_ID)
opp = away if is_home else home
opp_id = opp["id"]

c1, c2 = st.columns([1, 8])
with c1:
    ui_utils.load_image(opp["logo"], size=56, alt=opp["name"])
with c2:
    st.subheader(f"🆚 Próximo adversário: {opp['name']}")
    try:
        dt = pd.to_datetime(fx["fixture"]["date"])
        st.caption(f"Data: {dt.strftime('%d/%m/%Y %H:%M')} • Rodada: {fx['league'].get('round')}")
    except Exception:
        st.caption(f"Rodada: {fx['league'].get('round')}")

st.markdown("---")

# ---------------------------------------------------------------------
# 2) Forma recente do adversário (últimos 5 finalizados)
# ---------------------------------------------------------------------
st.markdown("### 📈 Forma recente (últimos 5 jogos)")
st.caption("**O que é**: últimos 5 jogos finalizados do adversário na temporada corrente (placar e resultado do ponto de vista do adversário).")

opp_fixtures_all = api_client.fixtures(opp_id, season) or []
for m in opp_fixtures_all:
    m["_d"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
opp_finals = [m for m in sorted(opp_fixtures_all, key=lambda x: x.get("_d") or pd.Timestamp(0), reverse=True) if _is_final(m)]
opp_last5 = opp_finals[:5]

rows = []
for it in opp_last5:
    f = it["fixture"]
    h, a = it["teams"]["home"], it["teams"]["away"]
    opp_home = (h["id"] == opp_id)
    gf = it["goals"]["home"] if opp_home else it["goals"]["away"]
    ga = it["goals"]["away"] if opp_home else it["goals"]["home"]
    res = "-"  # do ponto de vista do adversário
    if gf is not None and ga is not None:
        res = "V" if gf > ga else ("D" if gf < ga else "E")
    rows.append({
        "Data": str(f["date"])[:10],
        "Adversário": a["name"] if opp_home else h["name"],
        "Placar": _fmt_score(gf, ga),
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

# estatísticas do time: usaremos tanto team_statistics quanto fixtures->statistics
opp_stats = api_client.team_statistics(league["league_id"], season, opp_id) or {}
if isinstance(opp_stats, list):
    opp_stats = opp_stats[0] if opp_stats else {}

# coleto estatísticas jogo a jogo (limito a 10 para performance)
take_n = min(10, len(opp_finals))
shots, sots, poss, pass_acc, corners_for, corners_against = [], [], [], [], [], []
for it in opp_finals[:take_n]:
    try:
        blocks = api_client.fixture_statistics(it["fixture"]["id"]) or []
    except Exception:
        blocks = []
    my_items, opp_items = [], []
    for b in blocks:
        tid = (b.get("team") or {}).get("id")
        if tid == opp_id:
            my_items = b.get("statistics") or []
        else:
            opp_items = b.get("statistics") or []
    shots.append(_safe_pct(next((x.get("value") for x in my_items if (x.get("type") or "").lower() in ["total shots","shots total","shots"]), None)))
    sots.append(_safe_pct(next((x.get("value") for x in my_items if (x.get("type") or "").lower() in ["shots on goal","shots on target","sot"]), None)))
    poss.append(_safe_pct(next((x.get("value") for x in my_items if (x.get("type") or "").lower() in ["ball possession","possession"]), None)))
    pass_acc.append(_safe_pct(next((x.get("value") for x in my_items if "pass" in (x.get("type") or "").lower() and "%" in str(x.get("value"))), None)))
    corners_for.append(_safe_pct(next((x.get("value") for x in my_items if "corner" in (x.get("type") or "").lower()), None)))
    corners_against.append(_safe_pct(next((x.get("value") for x in opp_items if "corner" in (x.get("type") or "").lower()), None)))

# GF/GA médias da temporada
try:
    gf_avg = float(((opp_stats.get("goals") or {}).get("for") or {}).get("average", {}).get("total"))
except Exception:
    gf_avg = None
try:
    ga_avg = float(((opp_stats.get("goals") or {}).get("against") or {}).get("average", {}).get("total"))
except Exception:
    ga_avg = None

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Gols Pró/jogo", "—" if gf_avg is None else round(gf_avg, 2))
k2.metric("Gols Contra/jogo", "—" if ga_avg is None else round(ga_avg, 2))
k3.metric("SOT/jogo", "—" if _avg(sots) is None else _avg(sots))
k4.metric("Posse (%)", "—" if _avg(poss) is None else _avg(poss))
k5.metric("Passes certos (%)", "—" if _avg(pass_acc) is None else _avg(pass_acc))
k6.metric("Escanteios/jogo", "—" if _avg(corners_for) is None else _avg(corners_for))

st.markdown("---")

# ---------------------------------------------------------------------
# 4) Forças e Fragilidades (heurísticas simples)
# ---------------------------------------------------------------------
st.markdown("### 🧭 Forças & Fragilidades (heurísticas)")

def minute_bucket(block, side, rng):
    try:
        return (((block.get("goals") or {}).get(side) or {}).get("minute") or {}).get(rng, {}).get("total")
    except Exception:
        return None

bullets_str, bullets_weak = [], []
# Tendência de marcar no fim (76-90)
m_fin = _safe_pct(minute_bucket(opp_stats, "for", "76-90"))
if m_fin and m_fin >= 4:
    bullets_str.append("Marca frequentemente entre **76–90'**.")

# Tendência de sofrer no fim
s_fin = _safe_pct(minute_bucket(opp_stats, "against", "76-90"))
if s_fin and s_fin >= 4:
    bullets_weak.append("Costuma **sofrer gols no fim (76–90')**.")

# Conversão recente (gols/SOT) nas últimas partidas
if _avg(sots) and _avg(sots) > 0:
    conv = round(((_avg(sots) and sum([x for x in sots if x is not None])) and 0), 2)  # não usamos soma direta aqui
# Usamos heurísticas simples baseadas em GF/GA:
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
# 5) Head-to-Head (H2H)
# ---------------------------------------------------------------------
st.markdown("### 🤝 Confrontos diretos (H2H)")
st.caption("**O que é**: últimos confrontos entre Coritiba e o adversário na base da API.")

h2h = api_client.api_get("fixtures/headtohead", {"h2h": f"{OUR_ID}-{opp_id}", "last": 10}) or []
# h2h retorna fixtures em order desc normalmente – garantimos ordem por data:
for m in h2h:
    try:
        m["_d"] = pd.to_datetime(m["fixture"]["date"])
    except Exception:
        m["_d"] = pd.NaT
h2h = sorted(h2h, key=lambda x: x.get("_d") or pd.Timestamp(0), reverse=True)

rows_h2h = []
w = d = l = 0
for it in h2h[:10]:
    f = it["fixture"]
    h, a = it["teams"]["home"], it["teams"]["away"]
    our_home = (h["id"] == OUR_ID)
    gf = it["goals"]["home"] if our_home else it["goals"]["away"]
    ga = it["goals"]["away"] if our_home else it["goals"]["home"]
    res = "-"
    if gf is not None and ga is not None:
        if gf > ga:
            res = "V"; w += 1
        elif gf < ga:
            res = "D"; l += 1
        else:
            res = "E"; d += 1
    rows_h2h.append({
        "Data": str(f["date"])[:10],
        "Coritiba": it["teams"]["home"]["name"] if our_home else it["teams"]["away"]["name"],
        "Adversário": it["teams"]["away"]["name"] if our_home else it["teams"]["home"]["name"],
        "Placar": _fmt_score(gf, ga),
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

# médias do Coxa (temporada atual)
coxa_fixtures = api_client.fixtures(OUR_ID, season) or []
for m in coxa_fixtures:
    m["_d"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
coxa_finals = [m for m in coxa_fixtures if _is_final(m)]
gf_list = []; ga_list = []
for it in coxa_finals:
    h, a = it["teams"]["home"], it["teams"]["away"]
    our_home = (h["id"] == OUR_ID)
    gf_list.append(it["goals"]["home"] if our_home else it["goals"]["away"])
    ga_list.append(it["goals"]["away"] if our_home else it["goals"]["home"])
coxa_gf = _avg(gf_list) or 1.0
coxa_ga = _avg(ga_list) or 1.0

# médias do adversário (da seção KPIs)
opp_gf = gf_avg or 1.0
opp_ga = ga_avg or 1.0

lam_us  = float(np.mean([coxa_gf, opp_ga]))
lam_them = float(np.mean([coxa_ga, opp_gf]))

def pois_pmf(k, lam):  # P(X=k)
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

max_goals = 5
grid = np.array([[pois_pmf(i, lam_us) * pois_pmf(j, lam_them)
                  for j in range(max_goals+1)] for i in range(max_goals+1)], dtype=float)
grid = grid / grid.sum()

# Prob. V/E/D depende de mandante/visitante
if is_home:
    p_win = float(np.triu(grid, 1).sum())
    p_lose = float(np.tril(grid, -1).sum())
else:
    # visitante: vitória quando gols NÓS > ELES também; apenas o "ponto de vista" muda no cabeçalho
    p_win = float(np.triu(grid, 1).sum())
    p_lose = float(np.tril(grid, -1).sum())
p_draw = float(np.trace(grid))

p_over25 = float(sum(grid[i, j] for i in range(max_goals+1) for j in range(max_goals+1) if i + j >= 3))
p_btts = float(sum(grid[i, j] for i in range(1, max_goals+1) for j in range(1, max_goals+1)))

cols = st.columns(3)
cols[0].metric("Vitória (Coxa)", f"{round(p_win*100,1)}%")
cols[1].metric("Empate", f"{round(p_draw*100,1)}%")
cols[2].metric("Derrota", f"{round(p_lose*100,1)}%")

cols = st.columns(3)
cols[0].metric("Over 2.5", f"{round(p_over25*100,1)}%")
cols[1].metric("BTTS", f"{round(p_btts*100,1)}%")
cols[2].metric("xG simples (Coxa)", round(lam_us, 2))

# top placares
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
# 7) Prévia IA do confronto (corrigido)
# ---------------------------------------------------------------------
st.markdown("### 🧠 Prévia IA do confronto")

# contexto do Coxa — últimos 10 finalizados
for m in coxa_finals:
    m["_d"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
coxa_finals = sorted(coxa_finals, key=lambda x: x["_d"] or pd.Timestamp(0), reverse=True)[:10]
ctx_last_coxa = []
for it in coxa_finals:
    h, a = it["teams"]["home"], it["teams"]["away"]
    our_home = (h["id"] == OUR_ID)
    gh = it["goals"]["home"]; ga = it["goals"]["away"]
    ctx_last_coxa.append({
        "date": str(it["fixture"]["date"])[:19],
        "home": h["name"], "away": a["name"],
        "score": f"{gh}-{ga}",
        "is_home": our_home
    })

# contexto do adversário — últimos 10 finalizados
ctx_last_opp = []
for it in opp_finals[:10]:
    h, a = it["teams"]["home"], it["teams"]["away"]
    opp_home = (h["id"] == opp_id)
    gh = it["goals"]["home"]; ga = it["goals"]["away"]
    ctx_last_opp.append({
        "date": str(it["fixture"]["date"])[:19],
        "home": h["name"], "away": a["name"],
        "score": f"{gh}-{ga}",
        "is_home": opp_home
    })

context = {
    "mode": "pre_match",
    "season": season,
    "league": league,
    "team": team,
    "opponent": {"id": opp_id, "name": opp["name"], "logo": opp["logo"]},
    "match": {
        "fixture_id": fx["fixture"]["id"],
        "date": fx["fixture"]["date"],
        "is_home": is_home,
        "round": fx["league"].get("round")
    },
    "team_stats": api_client.team_statistics(league["league_id"], season, OUR_ID),
    "opp_stats": opp_stats,
    "last_games_team": ctx_last_coxa,
    "last_games_opp": ctx_last_opp,
    "head_to_head": rows_h2h,
    "simple_poisson": {
        "lambda_team": lam_us,
        "lambda_opp": lam_them,
        "p_win": p_win, "p_draw": p_draw, "p_lose": p_lose,
        "top_scores": [{"score": f"{i}-{j}", "prob": round(p,4)} for i,j,p in top6]
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
                    st.caption(ins.get("type","pre_match"))
                    st.subheader(ins.get("title","(sem título)"))
                    st.write(ins.get("summary",""))

                    ev = ins.get("evidence") or []
                    if ev:
                        st.markdown("**Evidências**")
                        for e in ev:
                            lbl = e.get("label","-"); val = e.get("value","-")
                            base = e.get("baseline"); unit = e.get("unit","")
                            base_txt = f" • baseline: {base}" if base is not None else ""
                            st.markdown(f"- **{lbl}**: {val}{unit}{base_txt}")

                    meta = []
                    if ins.get("severity"): meta.append(f"Severidade: {ins['severity']}")
                    if ins.get("confidence") is not None: meta.append(f"Conf.: {ins['confidence']}")
                    if ins.get("timeframe"): meta.append(f"Janela: {ins['timeframe']}")
                    if meta:
                        st.caption(" • ".join(meta))
    except Exception as e:
        st.error(f"Falha ao gerar a prévia IA: {e}")

st.caption("Fontes: API-Football — /fixtures, /fixtures/statistics, /fixtures/headtohead, /teams/statistics (liga=72).")
