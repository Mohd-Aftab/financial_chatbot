import os


from langgraph.graph import StateGraph, START
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from dotenv import load_dotenv

from vector_store_manager import vector_store

from data_ingestion.earning_retriever import ingest_multiple_pdfs
from output_schemas.stock_schema import get_stock_symbol
from tools.news_ingestion_tool import ingest_company_news
from tools.rag_tool import rag_tool
from tools.stock_price_tool import get_stock_price

import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

import yfinance as yf

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class FinanceState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    
conn = sqlite3.connect(database="financebot.db", check_same_thread=False)
# Checkpointer
checkpointer = SqliteSaver(conn=conn)

tools = [get_stock_price, get_stock_symbol, rag_tool, ingest_company_news]

llm_with_tools = llm.bind_tools(tools)

tool_node = ToolNode(tools)

graph = StateGraph(FinanceState)

def chat_node(state: FinanceState) : 
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    
    return {
        "messages" : [response]
    }

graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)
graph.add_edge("tools", "chat_node")


chatbot = graph.compile(checkpointer=checkpointer)
chatbot1 = graph.compile()

def get_all_threads():
    all_threads = set()

    # None -> we need all the checkpoints present in db 
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    return list(all_threads)

