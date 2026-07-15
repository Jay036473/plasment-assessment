"""
Groq Chatbot with Chat History (like ChatGPT)
-----------------------------------------------
Features:
- Chat with any Groq model (Llama 3, Mixtral, Gemma, etc.)
- Sidebar with "New Chat" button
- All previous chats are saved and listed in the sidebar (click to reopen)
- Chats are saved to a local JSON file, so they survive even if you close
  and reopen the app (persistent storage, not just session memory)

HOW TO RUN:
1. Install dependencies:
       pip install streamlit groq

2. Get a free Groq API key from: https://console.groq.com/keys

3. Run the app:
       streamlit run groq_chatbot.py

4. Paste your Groq API key in the sidebar when the app opens.
"""

import streamlit as st
from groq import Groq
import json
import os
import uuid
from datetime import datetime

# ============================================================
# 1. CONFIG / CONSTANTS
# ============================================================

HISTORY_FILE = "chat_history.json"   # where all chats get saved on disk

AVAILABLE_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

st.set_page_config(page_title="Groq Chatbot", page_icon="💬", layout="wide")


# ============================================================
# 2. PERSISTENT STORAGE HELPERS (load/save chats to a JSON file)
# ============================================================

def load_all_chats():
    """Read all saved chats from disk. Returns a dict: {chat_id: chat_data}"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_all_chats(all_chats):
    """Write all chats back to disk."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chats, f, indent=2, ensure_ascii=False)


def create_new_chat():
    """Creates a new empty chat and makes it the active one."""
    chat_id = str(uuid.uuid4())
    st.session_state.all_chats[chat_id] = {
        "title": "New Chat",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "messages": []  # each item: {"role": "user"/"assistant", "content": "..."}
    }
    st.session_state.active_chat_id = chat_id
    save_all_chats(st.session_state.all_chats)


def delete_chat(chat_id):
    """Deletes a chat permanently."""
    if chat_id in st.session_state.all_chats:
        del st.session_state.all_chats[chat_id]
        save_all_chats(st.session_state.all_chats)
        # If we deleted the active chat, switch to another one (or make a new one)
        if st.session_state.active_chat_id == chat_id:
            if st.session_state.all_chats:
                st.session_state.active_chat_id = list(st.session_state.all_chats.keys())[0]
            else:
                create_new_chat()


# ============================================================
# 3. INITIALIZE SESSION STATE (runs once per browser session)
# ============================================================

if "all_chats" not in st.session_state:
    st.session_state.all_chats = load_all_chats()

if "active_chat_id" not in st.session_state:
    if st.session_state.all_chats:
        # Open the most recently created chat by default
        st.session_state.active_chat_id = list(st.session_state.all_chats.keys())[-1]
    else:
        create_new_chat()


# ============================================================
# 4. SIDEBAR: API key, model choice, new chat button, chat history list
# ============================================================

with st.sidebar:
    st.title("💬 Groq Chatbot")
    GROQ_API_KEY="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"
    api_key = GROQ_API_KEY#st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    model_choice = st.selectbox("Model", AVAILABLE_MODELS)

    st.divider()

    if st.button("➕ New Chat", use_container_width=True):
        create_new_chat()
        st.rerun()

    st.divider()
    st.subheader("Previous Chats")

    # Show newest chats first
    chat_ids_sorted = list(st.session_state.all_chats.keys())[::-1]

    for chat_id in chat_ids_sorted:
        chat = st.session_state.all_chats[chat_id]
        col1, col2 = st.columns([4, 1])

        with col1:
            # Highlight the active chat with a different button type
            is_active = (chat_id == st.session_state.active_chat_id)
            if st.button(
                chat["title"],
                key=f"select_{chat_id}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.active_chat_id = chat_id
                st.rerun()

        with col2:
            if st.button("🗑️", key=f"delete_{chat_id}"):
                delete_chat(chat_id)
                st.rerun()


# ============================================================
# 5. MAIN CHAT AREA
# ============================================================

active_chat = st.session_state.all_chats[st.session_state.active_chat_id]

st.header(active_chat["title"])

# --- Show all previous messages in this chat ---
for msg in active_chat["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat input box at the bottom ---
user_input = st.chat_input("Type your message here...")

if user_input:
    if not api_key:
        st.error("Please enter your Groq API key in the sidebar first.")
        st.stop()

    # 1) Save + show the user's message
    active_chat["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2) If this is the first message in the chat, use it as the chat title
    if active_chat["title"] == "New Chat":
        active_chat["title"] = user_input[:40] + ("..." if len(user_input) > 40 else "")

    # 3) Call the Groq API, streaming the reply
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_reply = ""

        try:
            client = Groq(api_key=api_key)

            # We send the FULL conversation so far, so the model has memory
            # of everything said earlier in this chat.
            groq_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in active_chat["messages"]
            ]

            stream = client.chat.completions.create(
                model=model_choice,
                messages=groq_messages,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                full_reply += delta
                placeholder.markdown(full_reply + "▌")

            placeholder.markdown(full_reply)

        except Exception as e:
            full_reply = f"⚠️ Error calling Groq API: {e}"
            placeholder.markdown(full_reply)

    # 4) Save assistant reply and persist everything to disk
    active_chat["messages"].append({"role": "assistant", "content": full_reply})
    save_all_chats(st.session_state.all_chats)
  
