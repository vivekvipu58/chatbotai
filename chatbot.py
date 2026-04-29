"""
chatbot.py — TIER 2: Inference Engine + TIER 3: Knowledge Base
AI Travel & Tourism Chatbot
Updated: Groq AI integration for intelligent fallback responses
"""

import sqlite3
import os
import re
import json
import random
from datetime import datetime

# ─────────────────────────────────────────────
# GROQ AI SETUP
# ─────────────────────────────────────────────
GROQ_API_KEY = "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"
GROQ_MODEL = "llama3-8b-8192"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def _ask_groq(user_message: str) -> str:
    """Call Groq API and return the response text."""
    try:
        import urllib.request
        import json as _json

        payload = _json.dumps({
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are TravelBot AI, a friendly and helpful travel & tourism assistant. "
                        "You specialize in travel packages, destinations, visa info, travel tips, "
                        "flight advice, packing guides, and holiday planning. "
                        "Keep responses concise, helpful, and enthusiastic. Use travel-related emojis. "
                        "If asked about something non-travel related, gently redirect to travel topics."
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 500,
            "temperature": 0.7,
        }).encode("utf-8")

        req = urllib.request.Request(
            GROQ_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        return None  # Fall back to static fallback if Groq fails


# ─────────────────────────────────────────────
# TIER 3 — DATABASE / KNOWLEDGE BASE
# ─────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "travel_bot.db")


def init_db():
    """Create tables and seed initial data if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS packages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            dest      TEXT NOT NULL,
            duration  TEXT NOT NULL,
            price     REAL NOT NULL,
            includes  TEXT NOT NULL,
            rating    REAL DEFAULT 4.5
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS learned_qa (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern   TEXT NOT NULL,
            response  TEXT NOT NULL,
            hits      INTEGER DEFAULT 0,
            created   TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            role      TEXT NOT NULL,
            message   TEXT NOT NULL,
            ts        TEXT NOT NULL
        )
    """)

    cur.execute("SELECT COUNT(*) FROM packages")
    if cur.fetchone()[0] == 0:
        seed_packages = [
            ("Bali Bliss",         "Bali, Indonesia",      "7 Days / 6 Nights",  1299, "Flights, Hotel, Breakfast, Tours",        4.8),
            ("Paris Romance",      "Paris, France",        "5 Days / 4 Nights",  1899, "Flights, Hotel, City Tour, Seine Cruise", 4.7),
            ("Safari Adventure",   "Nairobi, Kenya",       "8 Days / 7 Nights",  2499, "Flights, Lodge, All Meals, Game Drives",  4.9),
            ("Tokyo Explorer",     "Tokyo, Japan",         "6 Days / 5 Nights",  1699, "Flights, Hotel, Rail Pass, City Guide",   4.6),
            ("Maldives Escape",    "Maldives",             "5 Days / 4 Nights",  2999, "Flights, Water Villa, All-Inclusive",     5.0),
            ("New York City Rush", "New York, USA",        "4 Days / 3 Nights",  1199, "Flights, Hotel, NYC Pass, Times Square",  4.5),
            ("Santorini Sunset",   "Santorini, Greece",    "6 Days / 5 Nights",  1799, "Flights, Cave Hotel, Breakfast, Cruise",  4.8),
            ("Amazon Rainforest",  "Manaus, Brazil",       "7 Days / 6 Nights",  1599, "Flights, Eco-Lodge, All Meals, Jungle",   4.6),
            ("Dubai Luxury",       "Dubai, UAE",           "5 Days / 4 Nights",  1499, "Flights, 5-Star Hotel, Desert Safari",    4.7),
            ("Sri Lanka Heritage", "Colombo, Sri Lanka",   "6 Days / 5 Nights",   899, "Flights, Hotel, Cultural Tour, Tea",      4.5),
        ]
        for p in seed_packages:
            cur.execute(
                "INSERT INTO packages (name, dest, duration, price, includes, rating) VALUES (?,?,?,?,?,?)", p
            )

    conn.commit()
    conn.close()


def get_all_packages():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name, dest, duration, price, includes, rating FROM packages ORDER BY rating DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def search_packages(keyword: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    like = f"%{keyword}%"
    cur.execute(
        "SELECT name, dest, duration, price, includes, rating FROM packages "
        "WHERE LOWER(name) LIKE LOWER(?) OR LOWER(dest) LIKE LOWER(?)",
        (like, like),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_budget_packages(max_price: float):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT name, dest, duration, price, includes, rating FROM packages WHERE price <= ? ORDER BY price",
        (max_price,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def save_learned_qa(pattern: str, response: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO learned_qa (pattern, response, hits, created) VALUES (?, ?, 0, ?)",
        (pattern.lower().strip(), response.strip(), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_learned_response(user_input: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, pattern, response FROM learned_qa")
    rows = cur.fetchall()
    conn.close()

    tokens = set(user_input.lower().split())
    best_id, best_resp, best_score = None, None, 0

    for row_id, pattern, response in rows:
        pat_tokens = set(pattern.split())
        overlap = len(tokens & pat_tokens)
        score = overlap / max(len(pat_tokens), 1)
        if score > best_score and score >= 0.5:
            best_score = score
            best_resp = response
            best_id = row_id

    if best_id:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE learned_qa SET hits = hits + 1 WHERE id = ?", (best_id,))
        conn.commit()
        conn.close()

    return best_resp


def save_chat(role: str, message: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO chat_history (role, message, ts) VALUES (?, ?, ?)",
        (role, message, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_chat_history(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT role, message, ts FROM chat_history ORDER BY id DESC LIMIT ?", (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return list(reversed(rows))


# ─────────────────────────────────────────────
# STATIC KNOWLEDGE BASE
# ─────────────────────────────────────────────

STATIC_KB = {
    "hello": ["Hello! 😊 Welcome to TravelBot! How can I help you plan your dream trip today?",
              "Hi there! ✈️ I'm TravelBot. Ask me anything about travel and tourism!"],
    "hi": ["Hi! 👋 Ready to explore the world? Ask me about travel packages, destinations, or tips!"],
    "hey": ["Hey! 🌍 What destination are you dreaming of today?"],
    "good morning": ["Good morning! ☀️ A beautiful day to plan an adventure! How can I assist you?"],
    "good afternoon": ["Good afternoon! 🌤️ Planning a trip? I'm here to help!"],
    "good evening": ["Good evening! 🌙 Thinking about your next getaway? Let's plan it!"],
    "bye": ["Goodbye! ✈️ Safe travels and happy adventuring! Come back anytime!"],
    "goodbye": ["Farewell! 🌏 May all your journeys be wonderful. See you soon!"],
    "see you": ["See you! 👋 Bon voyage and safe travels!"],
    "thanks": ["You're welcome! 😊 Is there anything else I can help you with?"],
    "thank you": ["My pleasure! 🙏 Feel free to ask if you need more travel advice!"],
    "who are you": ["I'm TravelBot 🤖✈️ — your AI-powered travel and tourism assistant! I can help with packages, destinations, travel tips, visa info, and more!"],
    "what can you do": ["I can help you with:\n✅ Holiday packages & pricing\n✅ Destination recommendations\n✅ Travel tips & visa info\n✅ Budget travel planning\n✅ Weather & best travel times\n✅ Flight & hotel advice\nJust ask me anything!"],
    "help": ["Sure! Here's what I can help with:\n🏖️ 'Show me packages' — list all tours\n💰 'Packages under $1500' — budget search\n🌍 'Tell me about Bali' — destination info\n📋 'Travel tips' — useful advice\n✈️ 'Visa requirements' — entry info\nWhat would you like to know?"],
    "travel tips": ["Here are some top travel tips! 🧳\n1️⃣ Book flights 6-8 weeks in advance\n2️⃣ Always get travel insurance\n3️⃣ Keep digital copies of your documents\n4️⃣ Learn a few local phrases\n5️⃣ Carry local currency for small purchases\n6️⃣ Pack light — you'll thank yourself later!"],
    "packing tips": ["Smart packing tips! 🎒\n• Roll clothes to save space\n• Use packing cubes\n• Pack a universal adapter\n• Bring a portable power bank\n• Always pack meds in carry-on\n• Leave room for souvenirs!"],
    "visa": ["Visa requirements vary by country and passport. 🛂\nFor accurate info:\n• Visit the official embassy website\n• Check iVisa.com or Sherpa\n• Apply at least 4-6 weeks in advance\nWhich country are you traveling to?"],
    "visa requirements": ["Visa requirements depend on your nationality and destination. 📋\nTell me which country you're visiting and I'll guide you further!"],
    "travel insurance": ["Travel insurance is a must! 🛡️\nIt covers:\n✅ Medical emergencies abroad\n✅ Trip cancellations\n✅ Lost baggage\n✅ Flight delays\nRecommended providers: World Nomads, Allianz, AXA."],
    "best time to travel": ["Best travel times by region 🌤️:\n• Bali: April–October (dry season)\n• Europe: May–September\n• Maldives: November–April\n• Japan: March–May (cherry blossoms)\n• Africa Safari: June–October\nTell me your destination for specific advice!"],
    "currency": ["Currency tips 💵:\n• Always exchange at banks or official exchanges\n• Avoid airport exchange booths (poor rates)\n• Notify your bank before traveling\n• Use a no-foreign-fee credit card\n• Keep some local cash for emergencies"],
    "flight tips": ["Flight booking tips ✈️:\n• Use Google Flights or Skyscanner\n• Book Tuesday/Wednesday for best prices\n• Set price alerts for your route\n• Consider nearby airports\n• Check baggage fees before booking!"],
}

DESTINATIONS = {
    "bali": "🌴 Bali, Indonesia — The Island of Gods!\n• Best for: Beaches, temples, rice terraces, wellness\n• Best time: April–October\n• Currency: Indonesian Rupiah (IDR)\n• Language: Bahasa Indonesia\n• Must-see: Uluwatu Temple, Tegallalang Rice Terraces, Seminyak Beach\n• Avg budget: $50–$150/day",
    "paris": "🗼 Paris, France — The City of Love!\n• Best for: Art, culture, cuisine, romance\n• Best time: April–June, September–October\n• Currency: Euro (EUR)\n• Language: French\n• Must-see: Eiffel Tower, Louvre, Notre-Dame, Champs-Élysées\n• Avg budget: $150–$300/day",
    "tokyo": "🗾 Tokyo, Japan — Where Tradition Meets Future!\n• Best for: Technology, culture, food, anime\n• Best time: March–May, October–November\n• Currency: Japanese Yen (JPY)\n• Language: Japanese\n• Must-see: Shibuya Crossing, Mt. Fuji, Senso-ji, Akihabara\n• Avg budget: $100–$250/day",
    "maldives": "🏝️ Maldives — Paradise on Earth!\n• Best for: Luxury, snorkeling, overwater villas\n• Best time: November–April\n• Currency: Maldivian Rufiyaa (MVR)\n• Language: Dhivehi\n• Must-see: Overwater bungalows, coral reefs, bioluminescent beaches\n• Avg budget: $200–$800/day",
    "dubai": "🏙️ Dubai, UAE — City of the Future!\n• Best for: Luxury shopping, desert safari, skyscrapers\n• Best time: November–March\n• Currency: UAE Dirham (AED)\n• Language: Arabic (English widely spoken)\n• Must-see: Burj Khalifa, Dubai Mall, Desert Safari, Palm Jumeirah\n• Avg budget: $150–$400/day",
    "kenya": "🦁 Nairobi, Kenya — Heart of Africa!\n• Best for: Wildlife safari, nature, culture\n• Best time: June–October\n• Currency: Kenyan Shilling (KES)\n• Language: Swahili, English\n• Must-see: Masai Mara, Amboseli, Nairobi National Park\n• Avg budget: $80–$300/day",
    "greece": "⛵ Santorini, Greece — Aegean Dream!\n• Best for: Sunsets, architecture, beaches, cuisine\n• Best time: May–October\n• Currency: Euro (EUR)\n• Language: Greek\n• Must-see: Oia sunset, Akrotiri ruins, volcanic beaches, caldera views\n• Avg budget: $120–$350/day",
    "new york": "🗽 New York, USA — The City That Never Sleeps!\n• Best for: Culture, shopping, food, Broadway\n• Best time: April–June, September–November\n• Currency: US Dollar (USD)\n• Language: English\n• Must-see: Times Square, Central Park, Statue of Liberty, Brooklyn Bridge\n• Avg budget: $150–$400/day",
    "sri lanka": "🌿 Sri Lanka — Pearl of the Indian Ocean!\n• Best for: Culture, wildlife, beaches, tea estates\n• Best time: December–March (west coast)\n• Currency: Sri Lankan Rupee (LKR)\n• Language: Sinhala, Tamil\n• Must-see: Sigiriya Rock, Kandy Temple, Ella, Yala National Park\n• Avg budget: $40–$120/day",
    "brazil": "🌊 Amazon, Brazil — Lungs of the Earth!\n• Best for: Rainforest, wildlife, adventure\n• Best time: June–November (dry season)\n• Currency: Brazilian Real (BRL)\n• Language: Portuguese\n• Must-see: Amazon River, Rio de Janeiro, Iguazu Falls, Pantanal\n• Avg budget: $60–$200/day",
}


# ─────────────────────────────────────────────
# TIER 2 — INFERENCE ENGINE
# ─────────────────────────────────────────────

_training_state = {}  # session_id -> {step, pattern}


def _format_packages(packages: list) -> str:
    if not packages:
        return "😔 No packages found matching your request. Try a different search or ask me to show all packages!"

    lines = ["Here are the available travel packages! 🌍✈️\n"]
    for i, (name, dest, duration, price, includes, rating) in enumerate(packages, 1):
        stars = "⭐" * int(rating)
        lines.append(
            f"**{i}. {name}**\n"
            f"   📍 {dest}\n"
            f"   ⏱️ {duration}\n"
            f"   💰 ${price:,.0f} per person\n"
            f"   ✅ Includes: {includes}\n"
            f"   {stars} ({rating}/5)\n"
        )
    lines.append("Type the package name for more details, or ask about a specific destination!")
    return "\n".join(lines)


def _extract_budget(text: str):
    patterns = [
        r"\$\s*(\d[\d,]*)",
        r"(\d[\d,]+)\s*dollars?",
        r"under\s+(\d[\d,]+)",
        r"below\s+(\d[\d,]+)",
        r"less than\s+(\d[\d,]+)",
        r"budget.*?(\d[\d,]+)",
        r"(\d[\d,]+)\s*usd",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def _detect_destination(text: str):
    text_lower = text.lower()
    for dest_key in DESTINATIONS:
        if dest_key in text_lower:
            return dest_key
    return None


def _get_emotion(response_text: str) -> str:
    text = response_text.lower()
    if any(w in text for w in ["sorry", "not found", "cannot", "don't know"]):
        return "😔"
    elif any(w in text for w in ["great", "wonderful", "amazing", "fantastic"]):
        return "🤩"
    elif any(w in text for w in ["hello", "hi", "welcome", "good morning"]):
        return "😊"
    elif any(w in text for w in ["tip", "advice", "recommend"]):
        return "🧠"
    elif any(w in text for w in ["package", "tour", "price"]):
        return "✈️"
    else:
        return "🤖"


def get_response(user_input: str, session_id: str = "default") -> dict:
    """
    TIER 2 — Main inference engine.
    Priority: Training Mode > Packages/Destinations/KB > Learned QA > Groq AI > Fallback
    Returns: { "text": str, "emotion": str, "type": str }
    """
    raw = user_input.strip()
    text = raw.lower()

    # ── Training mode (multi-turn) ─────────────────────────────────
    if session_id in _training_state:
        state = _training_state[session_id]

        if state["step"] == "awaiting_response":
            pattern = state["pattern"]
            save_learned_qa(pattern, raw)
            del _training_state[session_id]
            resp = f"✅ Got it! I've learned:\n❓ *\"{pattern}\"* → 💬 *\"{raw}\"*\nThanks for teaching me! 🎓"
            return {"text": resp, "emotion": "🎓", "type": "learn_confirm"}

        elif state["step"] == "awaiting_pattern":
            _training_state[session_id] = {"step": "awaiting_response", "pattern": raw}
            return {
                "text": f"Great! Now what should I reply when someone asks:\n❓ *\"{raw}\"*\n\nType the answer you want me to give:",
                "emotion": "🤔",
                "type": "learn_step2",
            }

    # ── Training trigger ───────────────────────────────────────────
    if re.search(r"\b(teach|learn|train|add.*question|new.*question)\b", text):
        _training_state[session_id] = {"step": "awaiting_pattern"}
        return {
            "text": "🎓 Great! I'm ready to learn.\n\nWhat question or phrase should I learn to respond to?\n*(Type the question exactly as users would ask it)*",
            "emotion": "🎓",
            "type": "learn_start",
        }

    # ── Show all packages ──────────────────────────────────────────
    if re.search(r"\b(show|list|all|view|display|what|available)\b.*\b(package|tour|deal|trip|holiday|vacation)\b", text) \
            or re.search(r"\b(package|tour|deal|trip|holiday|vacation)\b.*\b(show|list|all|view|available)\b", text) \
            or text in ("packages", "tours", "deals", "holidays"):
        pkgs = get_all_packages()
        return {"text": _format_packages(pkgs), "emotion": "✈️", "type": "packages"}

    # ── Budget search ──────────────────────────────────────────────
    budget = _extract_budget(text)
    if budget and re.search(r"\b(under|below|less|budget|cheap|afford|price)\b", text):
        pkgs = get_budget_packages(budget)
        header = f"💰 Packages under ${budget:,.0f}:\n"
        return {"text": header + _format_packages(pkgs), "emotion": "💰", "type": "budget_packages"}

    # ── Destination info ───────────────────────────────────────────
    dest = _detect_destination(text)
    if dest and re.search(r"\b(tell|about|info|information|guide|describe|what.*like|details)\b", text):
        return {"text": DESTINATIONS[dest], "emotion": "🌍", "type": "destination_info"}

    # ── Static knowledge base lookup ──────────────────────────────
    kb_keys = list(STATIC_KB.keys())
    i = 0
    best_key = None
    best_score = 0
    while i < len(kb_keys):
        key = kb_keys[i]
        if key in text:
            score = len(key)
            if score > best_score:
                best_score = score
                best_key = key
        i += 1

    if best_key:
        responses = STATIC_KB[best_key]
        reply = random.choice(responses) if isinstance(responses, list) else responses
        emotion = _get_emotion(reply)
        return {"text": reply, "emotion": emotion, "type": "static_kb"}

    # ── Learned Q&A lookup ────────────────────────────────────────
    learned = get_learned_response(raw)
    if learned:
        return {"text": f"💡 {learned}", "emotion": "💡", "type": "learned"}

    # ── Destination name alone ────────────────────────────────────
    if dest:
        return {"text": DESTINATIONS[dest], "emotion": "🌍", "type": "destination_info"}

    # ── Groq AI fallback ──────────────────────────────────────────
    groq_reply = _ask_groq(raw)
    if groq_reply:
        return {"text": groq_reply, "emotion": "🤖", "type": "groq_ai"}

    # ── Final fallback ─────────────────────────────────────────────
    fallbacks = [
        "Hmm, I'm not sure about that! 🤔 Try asking me about travel packages, destinations, visa tips, or packing advice. Type **'help'** to see what I can do!",
        "I didn't quite catch that! 😅 I specialize in travel & tourism. Ask me about packages, destinations, travel tips, or type **'show packages'** to browse tours!",
        "Great question, but it's a bit outside my travel expertise! 🗺️ Try asking about destinations, tour packages, or travel advice. Or type **'teach me'** to add new answers!",
    ]
    return {"text": random.choice(fallbacks), "emotion": "🤷", "type": "fallback"}


# Initialize DB on import
init_db()
