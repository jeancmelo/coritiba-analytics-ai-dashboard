import os, requests
from typing import Dict, Any, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

BASE = "https://v3.football.api-sports.io"

def _get_secret(key: str) -> Optional[str]:
    val = os.getenv(key)
    if val: return val
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None

def _headers():
    key = _get_secret("APISPORTS_KEY")
    if not key:
        raise RuntimeError("APISPORTS_KEY não definida em ambiente/secrets.")
    return {"x-apisports-key": key}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(1, 2, 8))
def api_get(endpoint: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    r = requests.get(f"{BASE}/{endpoint}", headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("response", [])

def find_team(name="Coritiba"):
    r = api_get("teams", {"search": name})
    if not r: raise ValueError("Time não encontrado")
    it = r[0]
    return {
        "team_id": it["team"]["id"],
        "team_name": it["team"]["name"],
        "team_logo": it["team"]["logo"],
        "venue": it.get("venue", {}),
    }

def leagues_by_country(country="Brazil"):
    r = api_get("leagues", {"country": country})
    out=[]
    for it in r:
        lg = it.get("league", {})
        out.append({
            "league_id": lg.get("id"),
            "league_name": lg.get("name"),
            "league_logo": lg.get("logo"),
            "seasons": [s.get("year") for s in it.get("seasons", []) if s.get("year")]
        })
    return out

def autodetect_league(team_id: int, season: int, country="Brazil"):
    le = [l for l in leagues_by_country(country) if season in l["seasons"]]
    le = sorted(le, key=lambda x: (x["league_name"] not in ["Serie A","Serie B"], x["league_name"]))
    for lg in le:
        try:
            ts = api_get("teams/statistics", {"league": lg["league_id"], "season": season, "team": team_id})
            if ts: return lg
        except Exception:
            pass
    return None

def fixtures(team_id: int, season: int, **kw):
    p = {"team": team_id, "season": season}; p.update(kw)
    return api_get("fixtures", p)

def fixture_statistics(fixture_id: int):   return api_get("fixtures/statistics", {"fixture": fixture_id})
def fixture_events(fixture_id: int):       return api_get("fixtures/events", {"fixture": fixture_id})
def fixture_lineups(fixture_id: int):      return api_get("fixtures/lineups", {"fixture": fixture_id})
def fixture_players(fixture_id: int):      return api_get("fixtures/players", {"fixture": fixture_id})
def standings(league_id: int, season: int):return api_get("standings", {"league": league_id, "season": season})
def team_statistics(league_id: int, season: int, team_id: int):
    return api_get("teams/statistics", {"league": league_id, "season": season, "team": team_id})
