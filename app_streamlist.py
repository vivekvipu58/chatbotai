"""
app_streamlist.py
=================
TIER 1 — Natural Language Interface (Flask Web Application)

Run with:
    python app_streamlist.py
Then open:  http://127.0.0.1:5000
"""

from flask import Flask, render_template, request, jsonify, session
from chatbot import (
    get_response,
    db_save_chat,
    db_get_history,
    db_get_all_packages,
    db_search_packages,
    db_get_budget_packages,
    db_save_learned,
    init_database,
)
import os
import uuid

# ──────────────────────────────────────────────────────────────
# FLASK APP SETUP
# ──────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "travelbot-secret-2025")

# Ensure DB is ready before first request
init_database()


# ──────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────

@app.route("/")
def home():
    """Render the main chatbot interface (Tier 1 — NL Interface)."""
    # Create a unique session ID for multi-turn training tracking
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/get_response", methods=["POST"])
def chat():
    """
    Inference Engine endpoint.
    Receives user message → calls Tier 2 (chatbot.py) → returns reply.
    """
    data       = request.get_json()
    user_msg   = data.get("message", "").strip()
    session_id = session.get("session_id", "default")

    if not user_msg:
        return jsonify({"reply": "Please type a message!", "emotion": "😅"})

    # Save user turn to DB
    db_save_chat("user", user_msg)

    # ── TIER 2: Inference Engine ──
    result = get_response(user_msg, session_id)

    # Save bot reply to DB
    db_save_chat("assistant", result["reply"])

    return jsonify({
        "reply":   result["reply"],
        "emotion": result["emotion"],
        "type":    result["type"],
    })


@app.route("/packages", methods=["GET"])
def packages():
    """Return all packages as JSON (used by the package table in the UI)."""
    rows = db_get_all_packages()
    # FOR LOOP — convert DB tuples to dicts
    result = []
    for row in rows:
        name, dest, duration, price, pkg_type, season, attractions, hotel, food, transport, rating = row
        result.append({
            "name": name, "destination": dest, "duration": duration,
            "price": price, "package_type": pkg_type, "season": season,
            "attractions": attractions, "hotel": hotel,
            "food": food, "transport": transport, "rating": rating,
        })
    return jsonify(result)


@app.route("/history", methods=["GET"])
def history():
    """Return recent chat history as JSON."""
    rows = db_get_history(30)
    # FOR LOOP — convert tuples to dicts
    result = []
    for role, message, ts in rows:
        result.append({"role": role, "message": message, "ts": ts[:16]})
    return jsonify(result)


@app.route("/teach", methods=["POST"])
def teach():
    """
    Direct teach endpoint — allows saving a Q&A pair via API.
    (Used as a fallback / admin endpoint.)
    """
    data     = request.get_json()
    question = data.get("question", "").strip()
    answer   = data.get("answer", "").strip()

    if not question or not answer:
        return jsonify({"reply": "Both question and answer are required.", "emotion": "❌"})

    db_save_learned(question, answer)
    return jsonify({
        "reply":   f"✅ Learned: '{question}' → '{answer}'",
        "emotion": "🎓",
    })


@app.route("/search_packages", methods=["POST"])
def search_packages_route():
    """Search packages by keyword."""
    data    = request.get_json()
    keyword = data.get("keyword", "").strip()
    rows    = db_search_packages(keyword)

    # FOR LOOP — build response list
    result = []
    for row in rows:
        name, dest, duration, price, pkg_type, season, attractions, hotel, food, transport, rating = row
        result.append({
            "name": name, "destination": dest, "duration": duration,
            "price": price, "package_type": pkg_type, "rating": rating,
        })
    return jsonify(result)


# ──────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("   ✈️  SMART TRAVEL CHATBOT — Starting Up")
    print("=" * 50)
    print("  Open your browser at:  http://127.0.0.1:5000")
    print("  Press CTRL+C to stop the server.")
    print("=" * 50)
    app.run(debug=True, port=5000)
