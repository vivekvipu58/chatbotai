"""
app_streamlit.py — TIER 1: Natural Language Interface
AI Travel & Tourism Chatbot — Updated with Groq AI + Sidebar Chat History
Run with: streamlit run app_streamlit.py
"""

import streamlit as st
import uuid
import os
from chatbot import get_response, get_chat_history, save_chat, get_all_packages, init_db

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="TravelBot AI",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# LOAD CUSTOM CSS
# ─────────────────────────────────────────────
css_path = os.path.join(os.path.dirname(__file__), "static", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "text": (
                "👋 Welcome to **TravelBot AI** — your smart travel & tourism assistant!\n\n"
                "I can help you with:\n"
                "✈️ Holiday packages & pricing\n"
                "🌍 Destination guides\n"
                "💡 Travel tips & visa info\n"
                "🎓 You can even **teach me** new things!\n\n"
                "Type **'show packages'** to start exploring or ask me anything!"
            ),
            "emotion": "😊",
        }
    ]

# Ensure DB is ready
init_db()

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ✈️ TravelBot AI")
    st.markdown("---")
    st.markdown("### 🚀 Quick Actions")

    quick_actions = [
        ("🌍 Show All Packages", "show all packages"),
        ("💰 Budget Under $1500", "packages under $1500"),
        ("🏖️ Bali Info", "tell me about Bali"),
        ("🗼 Paris Info", "tell me about Paris"),
        ("🦁 Safari Package", "show safari package"),
        ("✈️ Flight Tips", "flight tips"),
        ("🧳 Packing Tips", "packing tips"),
        ("🛂 Visa Info", "visa requirements"),
        ("🛡️ Travel Insurance", "travel insurance"),
        ("🌤️ Best Time to Travel", "best time to travel"),
        ("🎓 Teach Me Something", "teach me"),
    ]

    for label, action in quick_actions:
        if st.button(label, use_container_width=True, key=f"btn_{action}"):
            st.session_state.messages.append({"role": "user", "text": action, "emotion": "👤"})
            response = get_response(action, st.session_state.session_id)
            st.session_state.messages.append({
                "role": "assistant",
                "text": response["text"],
                "emotion": response["emotion"],
            })
            save_chat("user", action)
            save_chat("assistant", response["text"])
            st.rerun()

    st.markdown("---")
    st.markdown("### 📊 Stats")
    packages = get_all_packages()
    st.metric("Available Packages", len(packages))
    st.metric("Messages Today", len(st.session_state.messages))

    st.markdown("---")

    # Clear Chat button
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = [st.session_state.messages[0]]
        st.rerun()

    # Browse Packages — moved to sidebar
    with st.expander("📋 Browse All Packages"):
        pkgs = get_all_packages()
        if pkgs:
            import pandas as pd
            table_data = []
            for name, dest, duration, price, includes, rating in pkgs:
                stars = "⭐" * int(rating)
                table_data.append({
                    "Package": name,
                    "Destination": dest,
                    "Price": f"${price:,.0f}",
                    "Rating": f"{stars} {rating}",
                })
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No packages available.")

    # Chat History — added in sidebar after Clear Chat
    with st.expander("🗂️ Chat History"):
        history = get_chat_history(20)
        if history:
            for role, message, ts in history:
                icon = "👤" if role == "user" else "🤖"
                short_msg = message[:100] + "..." if len(message) > 100 else message
                st.markdown(f"**{icon} {role.title()}** `{ts[:16]}`\n> {short_msg}")
                st.markdown("---")
        else:
            st.info("No conversation history yet.")

    st.markdown("---")
    st.markdown("**TravelBot AI v1.0**\n\nPowered by Python + SQLite + Groq AI")


# ─────────────────────────────────────────────
# MAIN CHAT AREA
# ─────────────────────────────────────────────
st.markdown("# ✈️ TravelBot AI")
st.markdown("*Your intelligent travel & tourism assistant*")
st.markdown("---")

chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        role = msg["role"]
        text = msg["text"]
        emotion = msg.get("emotion", "🤖")

        if role == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(text)
        else:
            with st.chat_message("assistant", avatar="🤖"):
                col1, col2 = st.columns([0.08, 0.92])
                with col1:
                    st.markdown(
                        f"<div style='font-size:2rem;text-align:center'>{emotion}</div>",
                        unsafe_allow_html=True,
                    )
                with col2:
                    st.markdown(text)

# ─────────────────────────────────────────────
# INPUT AREA — no looping fix
# ─────────────────────────────────────────────
user_input = st.chat_input("Ask me about travel packages, destinations, tips... or type 'help'!")

if user_input and user_input.strip():
    user_text = user_input.strip()

    # Guard against duplicate last message (prevents re-run loop)
    last_user_msgs = [m for m in st.session_state.messages if m["role"] == "user"]
    if last_user_msgs and last_user_msgs[-1]["text"] == user_text:
        st.stop()

    st.session_state.messages.append({"role": "user", "text": user_text, "emotion": "👤"})
    save_chat("user", user_text)

    response = get_response(user_text, st.session_state.session_id)

    st.session_state.messages.append({
        "role": "assistant",
        "text": response["text"],
        "emotion": response["emotion"],
    })
    save_chat("assistant", response["text"])

    st.rerun()

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown(
    "<br><div style='text-align:center;color:#888;font-size:0.85rem'>"
    "TravelBot AI — Three-Tier Architecture: NL Interface | Groq AI Engine | SQLite Knowledge Base"
    "</div>",
    unsafe_allow_html=True,
)
