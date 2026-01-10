import streamlit as st
import uuid

from financial_bot_backend import chatbot, get_all_threads
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    AIMessageChunk,
)

from vector_store_manager import vector_store
from utils.prompts import SYSTEM_PROMPT


# ---------------- Utils ----------------

def generate_thread_id():
    return str(uuid.uuid4())


def inject_system_prompt(thread_id: str):
    """
    Inject system prompt ONCE per thread if not already present.
    """
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
        # Ignore SystemMessages and tool-only messages
        if isinstance(msg, (HumanMessage, AIMessage)) and msg.content:
            if hasattr(msg, "additional_kwargs") and msg.additional_kwargs.get(
                "tool_calls"
            ):
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
        temp_messages = []

        for msg in messages:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            temp_messages.append({"role": role, "content": msg.content})

        st.session_state["message_history"] = temp_messages


# ---------------- Main UI ----------------

st.title("📊 Financial Market Assistant")

CONFIG = {"configurable": {"thread_id": st.session_state["thread_id"]}}

# Render chat history
for msg in st.session_state.message_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


user_input = st.chat_input("Ask about stocks, earnings, or news...")

if user_input:
    # Show user message
    st.session_state.message_history.append(
        {"role": "user", "content": user_input}
    )
    with st.chat_message("user"):
        st.markdown(user_input)

    # IMPORTANT: send ONLY new message
    input_state = {
        "messages": [HumanMessage(content=user_input)]
    }

    with st.chat_message("assistant"):

        def stream_generator():
            for message_chunk, metadata in chatbot.stream(
                input_state,
                config=CONFIG,
                stream_mode="messages",
            ):
                # ❌ Ignore tool outputs completely
                if metadata.get("langgraph_node") == "tools":
                    continue

                if isinstance(message_chunk, AIMessageChunk) and message_chunk.content:
                    if message_chunk.content.strip().startswith("{"):
                        continue
                    yield message_chunk.content


        streamed_text = st.write_stream(stream_generator())

    # Save assistant response
    st.session_state.message_history.append(
        {"role": "assistant", "content": streamed_text}
    )
