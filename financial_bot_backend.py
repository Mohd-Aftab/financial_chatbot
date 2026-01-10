import os
from langgraph.graph import StateGraph, START
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from dotenv import load_dotenv

from vector_store_manager import vector_store

from tools.rag_tool import rag_tool, check_data_availability
from tools.news_ingestion_tool import ingest_company_news
from tools.stock_price_tool import get_stock_price, compare_stock_prices
from utils.company_resolver import resolve_company

import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class FinanceState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# Database connection for checkpointing
conn = sqlite3.connect(database="financebot.db", check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)


# Helper tool for company disambiguation
@tool
def clarify_company(company_query: str) -> dict:
    """
    Check if a company reference is ambiguous and get clarification options.
    
    Use this tool BEFORE other operations when:
    - User mentions a parent company (e.g., "Tata", "Alphabet")
    - Company name could refer to multiple entities
    - You want to ensure you're working with the right company
    
    Returns:
    - If unambiguous: resolved company info
    - If ambiguous: list of candidates for user to choose from
    """
    
    resolved, candidates = resolve_company(company_query, auto_select=False)
    
    if resolved:
        return {
            "is_ambiguous": False,
            "company": resolved.canonical_name,
            "ticker": resolved.ticker,
            "sector": resolved.sector,
            "message": f"Identified company: {resolved.canonical_name} ({resolved.ticker})"
        }
    
    elif candidates:
        candidates_list = [
            {
                "name": c.common_name,
                "canonical_name": c.canonical_name,
                "ticker": c.ticker,
                "description": c.description,
                "exchange": c.exchange
            }
            for c in candidates
        ]
        
        return {
            "is_ambiguous": True,
            "candidates": candidates_list,
            "message": f"Found {len(candidates)} possible companies for '{company_query}'. Please ask user to specify."
        }
    
    else:
        return {
            "is_ambiguous": False,
            "error": "not_found",
            "message": f"Could not find any company matching '{company_query}'"
        }


# Assemble all tools
tools = [
    get_stock_price,
    compare_stock_prices,
    rag_tool,
    check_data_availability,
    ingest_company_news,
    clarify_company,
]

llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)

# Build graph
graph = StateGraph(FinanceState)


def chat_node(state: FinanceState):
    """Main chat node with LLM + tools"""
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)
graph.add_edge("tools", "chat_node")

# Compile graph
chatbot = graph.compile(checkpointer=checkpointer)
chatbot1 = graph.compile()  # Without checkpointing


def get_all_threads():
    """Retrieve all conversation threads from database"""
    all_threads = set()
    
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    
    return list(all_threads)