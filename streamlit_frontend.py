import streamlit as st
import uuid
import time

from financial_bot_backend import chatbot, get_all_threads
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    AIMessageChunk,
)

from vector_store_manager import final_vector_store
from utils.prompt2 import SYSTEM_PROMPT


# ---------------- Custom CSS for Loader ----------------
st.markdown("""
<style>
    @keyframes pulse {
        0% { opacity: 0.4; transform: scale(0.98); }
        50% { opacity: 1; transform: scale(1); }
        100% { opacity: 0.4; transform: scale(0.98); }
    }
    .thinking-loader {
        display: flex;
        align-items: center;
        gap: 10px;
        font-family: sans-serif;
        color: #6c757d;
        font-style: italic;
        padding: 10px;
        animation: pulse 1.5s infinite ease-in-out;
    }
    .thinking-dots::after {
        content: ' .';
        animation: dots 1s steps(5, end) infinite;
    }
    @keyframes dots {
        0%, 20% { content: ' .'; }
        40% { content: ' ..'; }
        60% { content: ' ...'; }
        80%, 100% { content: ' '; }
    }
</style>
""", unsafe_allow_html=True)


# ---------------- Utils ----------------

def generate_thread_id():
    return str(uuid.uuid4())


def inject_system_prompt(thread_id: str):
    CONFIG = {"configurable": {"thread_id": thread_id}}
    state = chatbot.get_state(config=CONFIG)
    if not state.values or not state.values.get("messages"):
        chatbot.invoke(
            {"messages": [SystemMessage(content=SYSTEM_PROMPT)]},
            config=CONFIG,
        )


def reset_chat():
    thread_id = generate_thread_id()
    st.session_state.thread_id = thread_id
    st.session_state["chat_thread"].append(thread_id)
    st.session_state.message_history = []
    inject_system_prompt(thread_id)


def add_threads(thread_id):
    if thread_id not in st.session_state["chat_thread"]:
        st.session_state["chat_thread"].append(thread_id)
        inject_system_prompt(thread_id)


def load_conversation(thread_id):
    CONFIG = {"configurable": {"thread_id": thread_id}}
    state = chatbot.get_state(config=CONFIG)
    if not state.values or "messages" not in state.values:
        return []
    
    all_messages = state.values["messages"]
    clean_messages = []
    for msg in all_messages:
        if isinstance(msg, (HumanMessage, AIMessage)) and msg.content:
            if hasattr(msg, "additional_kwargs") and msg.additional_kwargs.get("tool_calls"):
                continue
            clean_messages.append(msg)
    return clean_messages


# ---------------- Session Setup ----------------

if "thread_id" not in st.session_state:
    st.session_state.thread_id = generate_thread_id()
    inject_system_prompt(st.session_state.thread_id)

if "message_history" not in st.session_state:
    st.session_state.message_history = []

if "chat_thread" not in st.session_state:
    st.session_state["chat_thread"] = get_all_threads()

add_threads(st.session_state["thread_id"])


# ---------------- Sidebar ----------------

st.sidebar.title("Financial Analyst Bot")

if st.sidebar.button("New Chat"):
    reset_chat()

st.sidebar.markdown(f"**Thread ID:** `{st.session_state.thread_id}`")
st.sidebar.header("My Conversations")

for thread_id in st.session_state["chat_thread"][::-1]:
    if st.sidebar.button(str(thread_id)):
        st.session_state["thread_id"] = thread_id
        inject_system_prompt(thread_id)
        messages = load_conversation(thread_id)
        
        # Helper to convert object to dict
        temp_messages = []
        for msg in messages:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            temp_messages.append({"role": role, "content": msg.content})
        
        st.session_state["message_history"] = temp_messages


# ---------------- Main UI ----------------

st.title("📊 Financial Market Assistant")

CONFIG = {"configurable": {"thread_id": st.session_state["thread_id"]}}

# deduplicate_history ensures we don't render the same message twice in a row
unique_history = []
if st.session_state.message_history:
    last_msg = None
    for msg in st.session_state.message_history:
        if last_msg and msg["role"] == last_msg["role"] and msg["content"] == last_msg["content"]:
            continue # Skip duplicate
        unique_history.append(msg)
        last_msg = msg
    # Update session state to the clean version
    st.session_state.message_history = unique_history

# Render chat history
for msg in st.session_state.message_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask about stocks, earnings, or news...")

if user_input:
    # 1. Append User Message immediately
    st.session_state.message_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. Prepare for Assistant Response
    input_state = {"messages": [HumanMessage(content=user_input)]}

    with st.chat_message("assistant"):
        # Enhanced CSS Loader
        loader_placeholder = st.empty()
        loader_placeholder.markdown(
            '<div class="thinking-loader">✨ Analyzing market data<span class="thinking-dots"></span></div>', 
            unsafe_allow_html=True
        )

        first_token = [True] 

        def stream_generator():
            for message_chunk, metadata in chatbot.stream(
                input_state,
                config=CONFIG,
                stream_mode="messages",
            ):
                if metadata.get("langgraph_node") == "tools":
                    continue

                if isinstance(message_chunk, AIMessageChunk) and message_chunk.content:
                    if message_chunk.content.strip().startswith("{"):
                        continue

                    # Clear loader immediately when first token arrives
                    if first_token[0]:
                        loader_placeholder.empty()
                        first_token[0] = False

                    yield message_chunk.content

        # Stream the response
        streamed_text = st.write_stream(stream_generator())

        # If for some reason stream didn't yield text (e.g. error), clear loader
        if first_token[0]: 
            loader_placeholder.empty()

    # 3. Append Assistant Message (Safely)
    if streamed_text:
        # Check against duplication before appending
        last_msg = st.session_state.message_history[-1] if st.session_state.message_history else None
        if not last_msg or last_msg.get("content") != streamed_text:
            st.session_state.message_history.append({"role": "assistant", "content": streamed_text})