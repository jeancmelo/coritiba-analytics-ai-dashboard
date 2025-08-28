# core/ai.py
import os, json, time
from typing import Any, Dict, List, Optional, Tuple

# OpenAI python >= 1.0
try:
    from openai import OpenAI
except Exception as e:  # pragma: no cover
    OpenAI = None

_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

class AIError(Exception):
    """Erro de alto nível para a camada de IA."""

def _make_client() -> OpenAI:
    if OpenAI is None:
        raise AIError("Pacote openai >=1.0 não está instalado.")
    if not os.getenv("OPENAI_API_KEY"):
        raise AIError("OPENAI_API_KEY não encontrada no ambiente.")
    return OpenAI()

def _json_schema() -> dict:
    # Schema simples de cartões de insight
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
                                        "value": {"type": ["string", "number"]},
                                        "baseline": {"type": ["string", "number", "null"]},
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
        "strict": True
    }

def _build_system_prompt(mode: str) -> str:
    base = (
        "Você é um analista tático/dados de futebol. "
        "Entregue insights claros e acionáveis sobre o Coritiba, em português do Brasil. "
        "Seja sucinto, sem jargões excessivos. Sempre explique por que importa e dê uma ação concreta."
    )
    if mode == "pre_match":
        base += " Foque em prévia do confronto (forças/fragilidades, bolas paradas, momentos de gol, riscos)."
    elif mode == "freeform":
        base += " Responda à pergunta do usuário usando o contexto e devolva como cartões de insight."
    else:
        base += " Gere de 3 a 6 cartões automáticos com base no contexto."
    return base

def _truncate_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Limita listas extensas para manter o payload enxuto e evitar erro por excesso."""
    ctx = dict(context)
    def tail(lst, n): 
        return list(lst)[-n:] if isinstance(lst, list) else lst
    ctx["last_games"] = tail(context.get("last_games", []), 10)
    if "last_games_team" in ctx:
        ctx["last_games_team"] = tail(ctx["last_games_team"], 10)
    if "last_games_opp" in ctx:
        ctx["last_games_opp"] = tail(ctx["last_games_opp"], 10)
    if "head_to_head" in ctx:
        ctx["head_to_head"] = tail(ctx["head_to_head"], 10)
    return ctx

def _call_openai(client: OpenAI, model: str, system: str, ctx: Dict[str, Any]) -> dict:
    """Chama Responses API pedindo JSON conforme schema."""
    resp = client.responses.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    "Gere cartões de insight no formato JSON (schema fornecido). "
                    "Contexto a seguir em JSON:\n\n" + json.dumps(ctx, ensure_ascii=False)
                ),
            },
        ],
        response_format={"type": "json_schema", "json_schema": _json_schema()},
        temperature=0.2,
    )
    # Em openai>=1.0, você consegue o texto direto:
    text = getattr(resp, "output_text", None)
    if not text:
        # fallback: coleta pedaços caso o provedor retorne segmentado
        try:
            parts = []
            for item in getattr(resp, "output", []) or []:
                for c in getattr(item, "content", []) or []:
                    if getattr(c, "type", "") == "output_text":
                        parts.append(getattr(c, "text", ""))
            text = "".join(parts).strip()
        except Exception:
            text = ""
    if not text:
        raise AIError("Resposta vazia do modelo.")
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and "insights" in payload:
            return payload
    except Exception as e:
        raise AIError(f"Falha ao parsear JSON da IA: {e}\nTrecho: {text[:400]}")
    raise AIError("Formato inválido recebido da IA.")

def _fallback_heuristics(context: Dict[str, Any]) -> dict:
    """Caso a IA falhe, gera alguns cartões básicos usando heurística."""
    last = context.get("last_games") or []
    gf = []
    ga = []
    for g in last:
        # tenta parse de score "x-y" se existir:
        sc = (g.get("score") or "").split("-")
        if len(sc) == 2:
            try:
                gf.append(float(sc[0])); ga.append(float(sc[1]))
            except Exception:
                pass
    insights = []
    if gf:
        media_gf = sum(gf)/len(gf)
        txt = f"Coritiba marcou em média {media_gf:.2f} gols nos últimos {len(gf)} jogos."
        insights.append({
            "type": "trend",
            "title": "Produção ofensiva recente",
            "summary": txt,
            "why_it_matters": "Ajuda a calibrar expectativa de gols na preparação do jogo.",
            "recommended_action": "Explorar padrões que levaram aos gols (ex.: cruzamentos, transições).",
            "severity": "low",
            "confidence": 0.6,
            "evidence": [{"label": "Gols por jogo (recente)", "value": round(media_gf,2)}],
        })
    if ga:
        media_ga = sum(ga)/len(ga)
        insights.append({
            "type": "risk",
            "title": "Gols sofridos recentes",
            "summary": f"O time sofreu {media_ga:.2f} gols/jogo nas últimas partidas.",
            "why_it_matters": "Indica ajustes defensivos necessários.",
            "recommended_action": "Trabalhar compactação e bolas paradas defensivas.",
            "severity": "medium" if media_ga>=1.5 else "low",
            "confidence": 0.6,
            "evidence": [{"label": "GA por jogo (recente)", "value": round(media_ga,2)}],
        })
    return {"insights": insights}

def generate_insights(
    context: Dict[str, Any],
    mode: Optional[str] = None,
    max_cards: int = 6,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Gera cartões de insight. 
    - mode: "auto" (default), "pre_match", "freeform"
    - context: dicionário leve; esta função já poda listas longas
    Retorna lista de dicts.
    Levanta AIError em erros críticos; usa fallback em último caso.
    """
    mode = mode or context.get("mode") or "auto"
    model = model or _DEFAULT_MODEL
    ctx = _truncate_context(context)

    try:
        client = _make_client()
        system = _build_system_prompt(mode)
        payload = _call_openai(client, model, system, ctx)
        insights = payload.get("insights") or []
        # saneamento
        clean = []
        for c in insights[:max_cards]:
            c["type"] = c.get("type") or mode
            c["summary"] = c.get("summary") or c.get("title") or ""
            c["evidence"] = c.get("evidence") or []
            clean.append(c)
        return clean
    except Exception as e:
        # último recurso: heurística
        try:
            fb = _fallback_heuristics(ctx).get("insights", [])
            if fb:
                return fb
        except Exception:
            pass
        # sem fallback: propaga com detalhe
        raise AIError(str(e)) from e
