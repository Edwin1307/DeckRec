from __future__ import annotations

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# App + middleware
# -----------------------------------------------------------------------------
app = FastAPI(title="DeckRec")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok for local dev
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(PROJECT_DIR)), name="static")

# -----------------------------------------------------------------------------
# Serve the frontend
# -----------------------------------------------------------------------------
@app.get("/")
def home():
    index_path = PROJECT_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(str(index_path))


@app.get("/health")
def health():
    return {"status": "ok"}


# -----------------------------------------------------------------------------
# Env / Clash API setup
# -----------------------------------------------------------------------------
env_path = PROJECT_DIR / ".env"
load_dotenv(dotenv_path=env_path)

CLASH_API_KEY = (os.getenv("CLASH_API_KEY") or "").strip().strip('"').strip("'")
if CLASH_API_KEY.lower().startswith("bearer "):
    CLASH_API_KEY = CLASH_API_KEY.split(" ", 1)[1].strip()

BASE_URL = "https://api.clashroyale.com/v1"
HEADERS = {
    "Authorization": f"Bearer {CLASH_API_KEY}",
    "Accept": "application/json",
}

# LLM provider config (optional)
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "none").strip().lower()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

_last_clash_error: Optional[str] = None


def fetch_all_cards() -> List[Dict[str, Any]]:
    """Fetch all cards from Clash Royale API. Returns [] on failure."""
    global _last_clash_error
    url = f"{BASE_URL}/cards"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            _last_clash_error = None
            data = r.json()
            return data.get("items", [])
        _last_clash_error = r.text
        return []
    except Exception as e:
        _last_clash_error = str(e)
        return []


# Cache cards at startup
cards_data: List[Dict[str, Any]] = fetch_all_cards()


def get_card_image(card_name: str) -> str:
    """Return the card icon URL (medium) if available, else empty string."""
    target = card_name.strip().lower()
    for card in cards_data:
        if str(card.get("name", "")).strip().lower() == target:
            icon_urls = card.get("iconUrls") or {}
            return icon_urls.get("medium", "") or ""
    return ""


@app.get("/debug/clash")
def debug_clash():
    """Quick sanity check endpoint."""
    return {
        "env_path": str(env_path),
        "env_exists": env_path.exists(),
        "token_length": len(CLASH_API_KEY),
        "token_masked": (CLASH_API_KEY[:6] + "..." + CLASH_API_KEY[-4:]) if CLASH_API_KEY else "",
        "last_clash_error": _last_clash_error,
        "cards_cached": len(cards_data),
        "auth_ok": len(cards_data) > 0 and _last_clash_error is None,
        "llm_provider": LLM_PROVIDER,
        "has_openai_key": bool(OPENAI_API_KEY),
        "has_groq_key": bool(GROQ_API_KEY),
    }


# -----------------------------------------------------------------------------
# Your current fixed decks (baseline fallback)
# -----------------------------------------------------------------------------
decks_by_bracket = {
    "<2000": {
        "attack": ["Hog Rider", "Knight", "Fire Spirits", "Zap", "Valkyrie", "Skeleton Army", "Arrows", "Musketeer"],
        "defense": ["Knight", "Mini PEKKA", "Archers", "Tombstone", "Arrows", "Fireball", "Baby Dragon", "Valkyrie"],
        "balance": ["Giant", "Mini PEKKA", "Musketeer", "Fireball", "Skeleton Army", "Arrows", "Knight", "Zap"],
    },
    "2000-4000": {
        "attack": ["Hog Rider", "Rage", "Mini PEKKA", "Valkyrie", "Arrows", "Fire Spirits", "Knight", "Musketeer"],
        "defense": ["Mega Knight", "Archers", "Tombstone", "Fireball", "Arrows", "Valkyrie", "Electro Wizard", "Knight"],
        "balance": ["Golem", "Musketeer", "Valkyrie", "Arrows", "Zap", "Skeleton Army", "Knight", "Baby Dragon"],
    },
    "4000-6000": {
        "attack": ["Balloon", "Miner", "Zap", "Inferno Tower", "Goblin Barrel", "Skeleton Army", "Knight", "Musketeer"],
        "defense": ["Mega Knight", "Electro Wizard", "Archers", "Tombstone", "Fireball", "Arrows", "Valkyrie", "Knight"],
        "balance": ["Golem", "Lava Hound", "Miner", "Zap", "Arrows", "Baby Dragon", "Knight", "Mega Minion"],
    },
    ">6000": {
        "attack": ["E-Giant", "Ram Rider", "Lightning", "Zap", "Bandit", "Musketeer", "Electro Wizard", "Skeleton Army"],
        "defense": ["P.E.K.K.A", "Mega Knight", "Electro Wizard", "Tornado", "Arrows", "Fireball", "Goblin Gang", "Valkyrie"],
        "balance": ["Royal Hogs", "Zappies", "Fireball", "Zap", "Musketeer", "Knight", "Baby Dragon", "Electro Wizard"],
    },
}

# -----------------------------------------------------------------------------
# API schema
# -----------------------------------------------------------------------------
class UserInput(BaseModel):
    bracket: str = Field(..., description="One of <2000, 2000-4000, 4000-6000, >6000")
    style: str = Field(..., description="attack, defense, balance")


class AIUserInput(UserInput):
    favorite_card: Optional[str] = Field(None, description="Optional: a card the user likes")
    hate_card: Optional[str] = Field(None, description="Optional: a card the user dislikes")
    notes: Optional[str] = Field(None, description="Optional: anything else e.g. 'struggle vs air'")


# -----------------------------------------------------------------------------
# Baseline endpoint
# -----------------------------------------------------------------------------
@app.post("/recommend_deck")
def recommend(input: UserInput):
    bracket = (input.bracket or "").strip()
    style = (input.style or "").strip().lower()

    if bracket not in decks_by_bracket:
        raise HTTPException(status_code=400, detail=f"Invalid bracket. Use: {list(decks_by_bracket.keys())}")
    if style not in decks_by_bracket[bracket]:
        raise HTTPException(status_code=400, detail=f"Invalid style. Use: {list(decks_by_bracket[bracket].keys())}")

    cards = decks_by_bracket[bracket][style]
    deck = [{"name": c, "image": get_card_image(c)} for c in cards]
    return {"deck": deck}


# -----------------------------------------------------------------------------
# LLM helpers (OpenAI or Groq) - optional
# -----------------------------------------------------------------------------
def _llm_chat(prompt: str) -> str:
    """
    Returns a raw string response from whichever provider is configured.
    Set in .env:
      LLM_PROVIDER=openai or groq
      OPENAI_API_KEY=...
      GROQ_API_KEY=...
    """
    provider = LLM_PROVIDER

    if provider == "openai":
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY missing in .env")
        # OpenAI Responses API (via HTTP to avoid extra SDK coupling)
        r = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4.1-mini",
                "input": prompt,
            },
            timeout=30,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=500, detail=f"OpenAI error: {r.text}")
        data = r.json()
        # Pull text safely
        try:
            return data["output"][0]["content"][0]["text"]
        except Exception:
            return json.dumps(data)

    if provider == "groq":
        if not GROQ_API_KEY:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY missing in .env")
        # Groq uses OpenAI-compatible chat completions
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=30,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=500, detail=f"Groq error: {r.text}")
        data = r.json()
        return data["choices"][0]["message"]["content"]

    raise HTTPException(
        status_code=400,
        detail="LLM_PROVIDER not set. Put LLM_PROVIDER=openai or LLM_PROVIDER=groq in .env to use AI endpoint.",
    )


@app.post("/recommend_deck_ai")
def recommend_ai(input: AIUserInput):
    """
    AI-generated deck + insights.
    Returns:
      { deck: [{name,image}...], insights: [..], playstyle_tips: [..] }
    """
    if not cards_data:
        raise HTTPException(status_code=503, detail="Cards not loaded from Clash API yet. Check /debug/clash")

    # Provide the model a shortlist of valid card names (so it doesn't hallucinate)
    valid_cards = [c.get("name") for c in cards_data if c.get("name")]

    user_pref = {
        "bracket": input.bracket,
        "style": input.style,
        "favorite_card": input.favorite_card,
        "hate_card": input.hate_card,
        "notes": input.notes,
    }

    prompt = f"""
You are a Clash Royale coach.

Task:
Generate ONE 8-card deck that matches the user's bracket and style, and give short actionable insights.

Constraints:
- You MUST pick card names ONLY from this allowed list: {valid_cards}
- Output MUST be valid JSON only (no markdown, no extra text).
- JSON shape:
{{
  "deck": ["Card1","Card2","Card3","Card4","Card5","Card6","Card7","Card8"],
  "insights": ["...","...","..."],
  "playstyle_tips": ["...","...","..."],
  "weaknesses": ["...","..."]
}}

User preferences:
{json.dumps(user_pref)}
""".strip()

    raw = _llm_chat(prompt)

    # Parse JSON safely
    try:
        result = json.loads(raw)
        deck_cards = result.get("deck", [])
        if not isinstance(deck_cards, list) or len(deck_cards) != 8:
            raise ValueError("deck must be a list of 8 cards")
    except Exception:
        # If model returns non-json sometimes, fail gracefully
        raise HTTPException(status_code=500, detail=f"AI response was not valid JSON. Raw: {raw[:500]}")

    deck = [{"name": c, "image": get_card_image(c)} for c in deck_cards]

    return {
        "deck": deck,
        "insights": result.get("insights", []),
        "playstyle_tips": result.get("playstyle_tips", []),
        "weaknesses": result.get("weaknesses", []),
    }
