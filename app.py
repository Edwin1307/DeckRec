from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()
API_KEY = os.getenv("CLASH_API_KEY")

BASE_URL = "https://api.clashroyale.com/v1"
headers = {
    "Authorization": f"Bearer {API_KEY}"
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fetch cards once at startup
def fetch_all_cards():
    try:
        url = f"{BASE_URL}/cards"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()["items"]
        else:
            print("Clash API Error:", response.text)
    except Exception as e:
        print("Failed loading cards:", e)
    return []

cards_data = fetch_all_cards()

def get_card_image(card_name: str):
    for card in cards_data:
        if card["name"].lower() == card_name.lower():
            return card["iconUrls"]["medium"]
    print(f"⚠️ Image not found for: {card_name}")
    return ""

decks_by_bracket = {
    "<2000": {
        "attack": ["Hog Rider", "Knight", "Fire Spirits", "Zap", "Valkyrie", "Skeleton Army", "Arrows", "Musketeer"],
        "defense": ["Knight", "Mini PEKKA", "Archers", "Tombstone", "Arrows", "Fireball", "Baby Dragon", "Valkyrie"],
        "balance": ["Giant", "Mini PEKKA", "Musketeer", "Fireball", "Skeleton Army", "Arrows", "Knight", "Zap"]
    },
    # (other brackets unchanged)
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
        "attack": ["E-Giant", "Ram Rider", "Lightning", "Zap", "Bandit", "Musketeer", "Electro Wizard", "Skeleton Army"],
        "defense": ["P.E.K.K.A", "Mega Knight", "Electro Wizard", "Tornado", "Arrows", "Fireball", "Goblin Gang", "Valkyrie"],
        "balance": ["Royal Hogs", "Zappies", "Fireball", "Zap", "Musketeer", "Knight", "Baby Dragon", "Electro Wizard"]
    }
}

class UserInput(BaseModel):
    bracket: str
    style: str

@app.post("/recommend_deck")
def recommend(input: UserInput):
    bracket = input.bracket
    style = input.style.lower()
    
    if bracket not in decks_by_bracket:
        return {"error": "Invalid bracket!"}
    
    if style not in decks_by_bracket[bracket]:
        return {"error": "Invalid style!"}
    
    cards = decks_by_bracket[bracket][style]
    deck = [{"name": c, "image": get_card_image(c)} for c in cards]
    
    return {"deck": deck}
