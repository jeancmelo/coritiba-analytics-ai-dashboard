# core/ai.py
import os, re, json
from typing import Any, Dict, List, Optional

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

def _build_system_prompt(mode: str) -> str:
    base = ("Você é um analista de dados/tático do Coritiba. "
            "Produza **cartões de insight** em pt-BR, concisos e acionáveis. ")
    if mode == "pre_match":
        base += "Foco em pré-jogo: forças, fragilidades, riscos e ações. "
    elif mode == "freeform":
        base += "Responda à pergunta do usuário como cartões. "
    else:
        base += "Gere 3–6 cartões automáticos a partir do contexto. "
    base += "Sempre explique por que importa e recomende uma ação."
    return base

def _tail(lst, n): 
    return list(lst)[-n:] if isinstance(lst, list) else lst

def _truncate_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(ctx)
    for k in ["last_games","last_games_team","last_games_opp","head_to_head"]:
        if k in c:
            c[k] = _tail(c[k], 10)
    for key in ["stats","team_stats","opp_stats"]:
        if key in c and isinstance(c[key], dict):
            s = c[key].copy()
            for big in ["fixtures","biggest","lineups","cards"]:
                s.pop(big, None)
            c[key] = s
    return c

def _extract_json(text: str) -> dict:
    if not text:
        raise AIError("Resposta vazia do modelo.")
    fenced = re.search(r"```json(.*?)```", text, re.S|re.I)
    if fenced:
        text = fenced.group(1)
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

# --------------------------- chamadas de IA ---------------------------

def _chat_json_object(client: OpenAI, model: str, system: str, ctx: dict) -> dict:
    """Primeira tentativa: Chat Completions com JSON obrigatório."""
    prompt = (
        "Responda **apenas** com JSON válido no formato:\n"
        '{"insights":[{"type":"trend","title":"...","summary":"...","why_it_matters":"...",'
        '"recommended_action":"...","timeframe":"", "severity":"low|medium|high", '
        '"confidence":0.0, "evidence":[{"label":"...","value":0,"baseline":0,"unit":""}]}]}\n\n'
        "Contexto:\n" + json.dumps(ctx, ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":prompt}],
        response_format={"type":"json_object"},
        temperature=0.2,
    )
    text = (resp.choices[0].message.content or "").strip()
    return _extract_json(text)

def _chat_plain_json(client: OpenAI, model: str, system: str, ctx: dict) -> dict:
    """Fallback: Chat Completions sem response_format, parseando o JSON do texto."""
    prompt = (
        "Retorne **apenas** JSON no formato informado (sem texto extra). "
        "Contexto:\n" + json.dumps(ctx, ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":prompt}],
        temperature=0.2,
    )
    text = (resp.choices[0].message.content or "").strip()
    return _extract_json(text)

# ------------------------------- público ------------------------------

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

    try:
        payload = _chat_json_object(client, model, system, ctx)
        return _normalize_cards(payload.get("insights", []), max_cards)
    except Exception as e1:
        try:
            payload = _chat_plain_json(client, model, system, ctx)
            return _normalize_cards(payload.get("insights", []), max_cards)
        except Exception as e2:
            raise AIError(f"Falha ao obter insights da IA. JSON object: {e1} | Plain: {e2}")
