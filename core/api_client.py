# core/api_client.py
from core.cache import get_json

# ------------------- TEAMS --------------------
def find_team(name: str):
    data = get_json("/teams", {"search": name})
    for item in data.get("response", []):
        team = item.get("team", {}) or {}
        if team.get("name", "").lower().startswith(name.lower()):
            venue = item.get("venue", {}) or {}
            return {
                "team_id": team.get("id"),
                "team_name": team.get("name"),
                "team_logo": team.get("logo"),
                "venue_name": venue.get("name"),
            }
    return None

# ------------------- LEAGUES --------------------
def autodetect_league(team_id: int, season: int, country: str):
    data = get_json("/leagues", {"team": team_id, "season": season, "country": country})
    # preferir Série B
    for item in data.get("response", []):
        lg = item.get("league", {}) or {}
        if lg.get("type") == "League" and "Serie B" in (lg.get("name") or ""):
            return {"league_id": lg["id"], "league_name": lg["name"], "league_logo": lg.get("logo")}
    # fallback
    if data.get("response"):
        lg = data["response"][0].get("league", {}) or {}
        return {"league_id": lg.get("id"), "league_name": lg.get("name"), "league_logo": lg.get("logo")}
    return None

# ------------------- STANDINGS --------------------
def standings(league_id: int, season: int):
    return get_json("/standings", {"league": league_id, "season": season}).get("response", [])

# ------------------- TEAM STATS --------------------
def team_statistics(league_id: int, season: int, team_id: int):
    return get_json("/teams/statistics", {"league": league_id, "season": season, "team": team_id})

# ------------------- FIXTURES --------------------
def fixtures(team_id: int, season: int, next: int | None = None):
    params = {"team": team_id, "season": season}
    if next:
        params["next"] = next
    return get_json("/fixtures", params).get("response", [])

def fixture_statistics(fixture_id: int):
    return get_json("/fixtures/statistics", {"fixture": fixture_id}).get("response", [])

def fixture_lineups(fixture_id: int):
    return get_json("/fixtures/lineups", {"fixture": fixture_id}).get("response", [])

def fixture_events(fixture_id: int):
    return get_json("/fixtures/events", {"fixture": fixture_id}).get("response", [])

# ------------------- PLAYERS --------------------
def players(team_id: int, season: int, page: int = 1):
    return get_json("/players", {"team": team_id, "season": season, "page": page}).get("response", [])
