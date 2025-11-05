from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjM2NzI0OTg2LTdiN2EtNDdlZC1hZmJhLWQ0NDNjYzc2YjkxMCIsImlhdCI6MTc2MjM4MTE1NSwic3ViIjoiZGV2ZWxvcGVyLzdiZWIxMjZhLTcxY2UtYjI2Yi02NDNlLWZlMmE2Yzc0MjAzMiIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyIxMjkuMTA3LjE5Mi43Il0sInR5cGUiOiJjbGllbnQifV19.cjdTU0alQoVoGGYn2uFDmhfqh_yWPX0u5Aq1GbLCy0xRe_gQjQGSQfxEgkbh4Ef1rCq0rI81P4mEr0LbBIDHfw"
BASE_URL = "https://api.clashroyale.com/v1"

headers = {"Authorization": f"Bearer {API_KEY}"}

def fetch_all_cards():
    url = f"{BASE_URL}/cards"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["items"]
    return []

cards_data = fetch_all_cards()

def get_card_image(card_name: str):
    for card in cards_data:
        if card["name"].lower() == card_name.lower():
            return card["iconUrls"]["medium"]
    return ""

# Define deck dictionaries keyed by trophy bracket and style
decks_by_bracket = {
    "<2000": {
        "attack": ["Hog Rider", "Knight", "Fire Spirits", "Zap", "Valkyrie", "Skeleton Army", "Arrows", "Musketeer"],
        "defense": ["Knight", "Mini PEKKA", "Archers", "Tombstone", "Arrows", "Fireball", "Baby Dragon", "Valkyrie"],
        "balance": ["Giant", "Mini PEKKA", "Musketeer", "Fireball", "Skeleton Army", "Arrows", "Knight", "Zap"]
    },
    "2000-4000": {
        "attack": ["Hog Rider", "Rage", "Mini PEKKA", "Valkyrie", "Arrows", "Fire Spirits", "Knight", "Musketeer"],
        "defense": ["Mega Knight", "Archers", "Tombstone", "Fireball", "Arrows", "Valkyrie", "Electro Wizard", "Knight"],
        "balance": ["Golem", "Musketeer", "Valkyrie", "Arrows", "Zap", "Skeleton Army", "Knight", "Baby Dragon"]
    },
    "4000-6000": {
        "attack": ["Balloon", "Miner", "Zap", "Inferno Tower", "Goblin Barrel", "Skeleton Army", "Knight", "Musketeer"],
        "defense": ["Mega Knight", "Electro Wizard", "Archers", "Tombstone", "Fireball", "Arrows", "Valkyrie", "Knight"],
        "balance": ["Golem", "Lava Hound", "Miner", "Zap", "Arrows", "Baby Dragon", "Knight", "Mega Minion"]
    },
    ">6000": {
        "attack": ["E‑Giant", "Ram Rider", "Lightning", "Zap", "Bandit", "Musketeer", "Electro Wizard", "Skeleton Army"],
        "defense": ["P.E.K.K.A", "Mega Knight", "Electro Wizard", "Tornado", "Arrows", "Fireball", "Goblin Gang", "Valkyrie"],
        "balance": ["Royal Hogs", "Zappies", "Fireball", "Zap", "Musketeer", "Knight", "Baby Dragon", "Electro Wizard"]
    }
}

class UserInput(BaseModel):
    bracket: str   # changed from trophies to bracket
    style: str

@app.post("/recommend_deck")
def recommend(input: UserInput):
    bracket = input.bracket
    style = input.style.lower()
    if bracket not in decks_by_bracket:
        return {"error": "Invalid trophy bracket!"}
    bracket_decks = decks_by_bracket[bracket]
    if style not in bracket_decks:
        return {"error": "Invalid style!"}
    card_names = bracket_decks[style]
    deck_with_images = [{"name": name, "image": get_card_image(name)} for name in card_names]
    return {"deck": deck_with_images}
