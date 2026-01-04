from financial_bot_backend import chatbot, vector_store
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

SYSTEM_PROMPT = """
You are a professional financial analyst specializing in stock markets, company fundamentals,
earnings, and market-moving news.

When the user asks about trends, stock movement, reasons, or specific news, you must:

1. Plan the necessary tool calls (symbol resolution, stock price, news ingestion).
2. Execute those tools without responding to the user during planning.
3. After all tool calls are done, call `rag_tool` to retrieve relevant context.
4. Only after RAG retrieval, produce a final, concise answer.

Do not produce intermediate replies such as 'Let me check' or 'Let me analyze'.
Only output after RAG context is available.
"""



initial_state = {
    "messages": [SystemMessage(content=SYSTEM_PROMPT)],
    "vector_store": vector_store
}

while True :
    
    user_input = input("User: ")
    
    if user_input.lower() in ["exit", "quit"]:
        break
    
    initial_state["messages"].append(HumanMessage(content=user_input))
    result = chatbot.invoke(initial_state)
    bot_response = result["messages"][-1]
    print("Bot:", bot_response.content)
    initial_state["messages"].append(AIMessage(content=bot_response.content))
