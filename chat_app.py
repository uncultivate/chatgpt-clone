from openai import OpenAI
import streamlit as st
import base64

st.title("JonoGPT")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 1

# Display Model
st.sidebar.write("Model: GPT 4o")
st.sidebar.divider()
# Moved file uploader below the chat input block
uploaded_files = st.sidebar.file_uploader("Vision", 
                                  accept_multiple_files=True, 
                                  type=["jpg", "jpeg", "png"],
                                  key=st.session_state["uploader_key"])

# Display uploaded images in the sidebar
if uploaded_files:
    for uploaded_file in uploaded_files:
        st.sidebar.image(uploaded_file, caption=uploaded_file.name, width=128)

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

        if uploaded_files:
            st.session_state["uploaded_files"] = uploaded_files
            st.session_state['uploader_key'] += 1
            st.rerun()
