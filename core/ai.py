# core/ai.py
import os, re, json, math
from typing import Any, Dict, List, Optional

# OpenAI python >= 1.0
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

class AIError(Exception):
    pass

# ------------------------------- utils -------------------------------

def _make_client() -> OpenAI:
    if OpenAI is None:
        raise AIError("Pacote openai>=1.0 não está instalado.")
    if not os.getenv("OPENAI_API_KEY"):
        raise AIError("OPENAI_API_KEY não definida no ambiente.")
    return OpenAI()

def _json_schema(strict: bool = False) -> dict:
    return {
        "name": "insights_payload",
        "schema": {
            "type": "object",
            "properties": {
                "insights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                            "why_it_matters": {"type": "string"},
                            "recommended_action": {"type": "string"},
                            "timeframe": {"type": "string"},
                            "severity": {"type": "string"},
                            "confidence": {"type": "number"},
                            "evidence": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "value": {"type": ["string","number"]},
                                        "baseline": {"type": ["string","number","null"]},
                                        "unit": {"type": "string"}
                                    },
                                    "required": ["label","value"]
                                }
                            }
                        },
                        "required": ["title","summary"]
                    }
                }
            },
            "required": ["insights"]
        },
        "strict": strict
    }

def _build_system_prompt(mode: str) -> str:
    base = ("Você é um analista de dados/tático do Coritiba. "
            "Produza **cartões de insight** em pt-BR, concisos e acionáveis.")
    if mode == "pre_match":
        base += " Foco em pré-jogo: forças, fragilidades, riscos e ações."
    elif mode == "freeform":
        base += " Responda à pergunta do usuário como cartões."
    else:
        base += " Gere 3–6 cartões automáticos a partir do contexto."
    base += " Sempre explique por que importa e recomende uma ação."
    return base

def _tail(lst, n): 
    return list(lst)[-n:] if isinstance(lst, list) else lst

def _truncate_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(ctx)
    for k in ["last_games","last_games_team","last_games_opp","head_to_head"]:
        if k in c:
            c[k] = _tail(c[k], 10)
    # evita stats gigantes
    if "stats" in c and isinstance(c["stats"], dict):
        s = c["stats"].copy()
        for big in ["fixtures","biggest","lineups","cards"]:
            s.pop(big, None)
        c["stats"] = s
    if "team_stats" in c and isinstance(c["team_stats"], dict):
        s = c["team_stats"].copy()
        for big in ["lineups","cards"]:
            s.pop(big, None)
        c["team_stats"] = s
    if "opp_stats" in c and isinstance(c["opp_stats"], dict):
        s = c["opp_stats"].copy()
        for big in ["lineups","cards"]:
            s.pop(big, None)
        c["opp_stats"] = s
    return c

def _extract_json(text: str) -> dict:
    """Extrai primeiro objeto JSON plausível de um texto (mesmo vindo em ```json ...```)."""
    if not text:
        raise AIError("Resposta vazia do modelo.")
    # remove cercas markdown
    fenced = re.search(r"```json(.*?)```", text, re.S|re.I)
    if fenced:
        text = fenced.group(1)
    # tenta achar primeiro bloco {...}
    brace = re.search(r"\{.*\}", text, re.S)
    if brace:
        text = brace.group(0)
    try:
        data = json.loads(text)
    except Exception as e:
        raise AIError(f"Falha ao parsear JSON: {e}\nTrecho: {text[:400]}")
    if not isinstance(data, dict) or "insights" not in data:
        raise AIError("JSON sem chave 'insights'.")
    return data

def _normalize_cards(cards: List[dict], max_cards: int) -> List[dict]:
    out = []
    for c in cards[:max_cards]:
        out.append({
            "type": c.get("type") or "insight",
            "title": c.get("title") or "(sem título)",
            "summary": c.get("summary") or "",
            "why_it_matters": c.get("why_it_matters") or "",
            "recommended_action": c.get("recommended_action") or "",
            "timeframe": c.get("timeframe") or "",
            "severity": c.get("severity") or "",
            "confidence": c.get("confidence"),
            "evidence": c.get("evidence") or [],
        })
    return out

# ------------------------------ core call -----------------------------

def _call_json_schema(client: OpenAI, model: str, system: str, ctx: dict) -> dict:
    """Primeira tentativa: pedir JSON validado por schema (strict=False)."""
    resp = client.responses.create(
        model=model,
        messages=[
            {"role":"system","content":system},
            {"role":"user","content":"Use o **formato JSON abaixo** e responda apenas com JSON.\n\nContexto:\n"+json.dumps(ctx, ensure_ascii=False)}
        ],
        response_format={"type":"json_schema","json_schema":_json_schema(strict=False)},
        temperature=0.2,
    )
    text = getattr(resp, "output_text", "") or ""
    if not text:
        # coleta pedacinhos, quando houver
        try:
            parts=[]
            for it in getattr(resp, "output", []) or []:
                for c in getattr(it, "content", []) or []:
                    if getattr(c, "type","") == "output_text":
                        parts.append(getattr(c, "text",""))
            text="".join(parts)
        except Exception:
            text=""
    return _extract_json(text)

def _call_json_plain(client: OpenAI, model: str, system: str, ctx: dict) -> dict:
    """Fallback: pedir JSON 'puro' sem schema e parsear."""
    prompt = (
        "Responda **apenas** com JSON, seguindo este formato:\n"
        '{"insights":[{"type":"trend","title":"...","summary":"...","why_it_matters":"...","recommended_action":"...",'
        '"timeframe":"", "severity":"low|medium|high", "confidence":0.0, "evidence":[{"label":"...","value":0,"baseline":0,"unit":""}]}]}\n\n'
        "Contexto:\n" + json.dumps(ctx, ensure_ascii=False)
    )
    resp = client.responses.create(
        model=model,
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        temperature=0.2,
    )
    text = getattr(resp, "output_text", "") or ""
    if not text:
        try:
            parts=[]
            for it in getattr(resp, "output", []) or []:
                for c in getattr(it, "content", []) or []:
                    if getattr(c, "type","") == "output_text":
                        parts.append(getattr(c, "text",""))
            text="".join(parts)
        except Exception:
            text=""
    return _extract_json(text)

# ------------------------------- public ------------------------------

def generate_insights(
    context: Dict[str, Any],
    mode: Optional[str] = None,
    max_cards: int = 6,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    mode = mode or context.get("mode") or "auto"
    model = model or _DEFAULT_MODEL
    ctx = _truncate_context(context)

    client = _make_client()
    system = _build_system_prompt(mode)

    # 1ª tentativa: schema
    try:
        payload = _call_json_schema(client, model, system, ctx)
        return _normalize_cards(payload.get("insights", []), max_cards)
    except Exception as e1:
        # 2ª tentativa: plain JSON
        try:
            payload = _call_json_plain(client, model, system, ctx)
            return _normalize_cards(payload.get("insights", []), max_cards)
        except Exception as e2:
            # por fim, um fallback mínimo
            raise AIError(f"Falha ao obter insights da IA. Schema: {e1} | Plain: {e2}")
