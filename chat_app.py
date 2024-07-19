from openai import OpenAI
import hmac
import streamlit as st
import base64
import sqlite3
import json
from datetime import datetime
from collections import defaultdict

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False


if not check_password():
    st.stop()  # Do not continue if check_password is not True.

# Initialize SQLite database
conn = sqlite3.connect('chat_history.db')
c = conn.cursor()

# Update table schema to include a summary field if not already present
c.execute('''
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY,
        conversation TEXT,
        summary TEXT,
        date TEXT
    )
''')
conn.commit()

st.title("JonoGPT")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o-mini"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 1

if "chat_id" not in st.session_state:
    st.session_state.chat_id = None

# Function to summarize the first message of a conversation
def summarize_first_message(conversation):
    first_message = json.loads(conversation)[0]["content"][0]["text"]
    summary_prompt = f"Summarize the following message into 3-4 words: {first_message}"
    
    response = client.chat.completions.create(
        model=st.session_state["openai_model"],
        messages=[{"role": "system", "content": summary_prompt}],
    )
    
    summary = response.choices[0].message.content.strip()
    return summary

# Function to save conversation to database
def save_conversation():
    if st.session_state.messages:
        conversation = json.dumps(st.session_state.messages)
        summary = summarize_first_message(conversation) if st.session_state.chat_id is None else None
        date = datetime.now().strftime("%Y-%m-%d")

        if st.session_state.chat_id is None:
            c.execute("INSERT INTO chats (conversation, summary, date) VALUES (?, ?, ?)", (conversation, summary, date))
            st.session_state.chat_id = c.lastrowid
        else:
            c.execute("UPDATE chats SET conversation = ? WHERE id = ?", (conversation, st.session_state.chat_id))
        conn.commit()

# Function to load conversation from database
def load_conversation(chat_id):
    c.execute("SELECT conversation FROM chats WHERE id = ?", (chat_id,))
    row = c.fetchone()
    if row:
        st.session_state.messages = json.loads(row[0])
        st.session_state.chat_id = chat_id

# Function to start a new chat
def new_chat():
    st.session_state.messages = []
    st.session_state.chat_id = None

# Function to clear all chat history
def clear_history():
    c.execute("DELETE FROM chats")
    conn.commit()
    new_chat()

# Display Model
st.sidebar.write("Version: 0.1")
st.sidebar.write("Model: GPT 4o")

# Create new chats
if st.sidebar.button("New Chat"):
        new_chat()

st.sidebar.divider()

# File uploader
uploaded_files = st.sidebar.file_uploader("Vision", 
                                          accept_multiple_files=True, 
                                          type=["jpg", "jpeg", "png"],
                                          key=st.session_state["uploader_key"])

# Display uploaded images in the sidebar
if uploaded_files:
    for uploaded_file in uploaded_files:
        st.sidebar.image(uploaded_file, caption=uploaded_file.name, width=128)

st.sidebar.divider()

# Function to categorize date
def categorize_date(chat_date):
    today = datetime.now().date()
    chat_date = datetime.strptime(chat_date, "%Y-%m-%d").date()
    delta = today - chat_date

    if delta.days == 0:
        return "Today"
    elif delta.days == 1:
        return "Yesterday"
    elif delta.days <= 7:
        return "Previous 7 Days"
    elif delta.days <= 30:
        return "Previous 30 Days"
    else:
        return "Older"

# Display old conversations grouped by categories
st.sidebar.write("Chat History")

c.execute("SELECT id, summary, date FROM chats ORDER BY date DESC")
chats = c.fetchall()

# Group chats by categories
chats_by_category = defaultdict(list)
for chat_id, summary, date in chats:
    category = categorize_date(date)
    chats_by_category[category].append((chat_id, summary, date))

# Order of categories
categories_order = ["Today", "Yesterday", "Previous 7 Days", "Previous 30 Days", "Older"]

for category in categories_order:
    if category in chats_by_category:
        st.sidebar.write(f"### {category}")
        for chat_id, summary, date in chats_by_category[category]:
            button_label = summary if summary else f"Conversation {chat_id} ({date})"
            if st.sidebar.button(button_label, use_container_width=True):
                load_conversation(chat_id)

st.sidebar.divider()
if st.sidebar.button("Clear History"):
    clear_history()



# Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            for content_item in message["content"]:
                if content_item["type"] == "text":
                    st.markdown(content_item["text"])
            if "images" in message:
                for img in message["images"]:
                    st.image(base64.b64decode(img), width=128)
        if message["role"] == "assistant":
            st.markdown(message["content"])

# Function to encode the image
def encode_image(image):
    return base64.b64encode(image.read()).decode('utf-8')

def contains_image(type):
    return type.startswith('image')

# Combined chat input
prompt = st.chat_input("Message ChatGPT")

if prompt:
    images = [encode_image(file) for file in uploaded_files] if uploaded_files else []
    
    content = [{"type": "text", "text": prompt}]
    
    if images:
        image_urls = [f"data:image/jpeg;base64,{img}" for img in images]
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
    
    st.session_state.messages.append({"role": "user", "content": content, "images": images})

    # Display user's prompt
    with st.chat_message("user"):
        st.markdown(prompt)
        if images:
            for img in images:
                st.image(base64.b64decode(img), width=128)

    # Save conversation
    save_conversation()

    # Send request to OpenAI
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
        )
        response = st.write_stream(stream)
        st.session_state.messages.append({"role": "assistant", "content": response})

        # Save conversation again with assistant's response
        save_conversation()

        if uploaded_files:
            st.session_state["uploaded_files"] = uploaded_files
            st.session_state['uploader_key'] += 1
            st.rerun()
