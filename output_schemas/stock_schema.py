from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from langchain_community.tools import DuckDuckGoSearchRun

# Initialize LLM and Search
llm = ChatOpenAI(temperature=0)
search = DuckDuckGoSearchRun()

class GetSymbol(BaseModel):
    symbol: str | None = Field(
        ...,
        description=(
            "The exact Yahoo Finance ticker symbol found from search results (e.g., 'TMPV.NS', 'AAPL'). "
            "Return None or 'PRIVATE' if the company is private/not listed."
        )
    )
    reason: str = Field(
        ...,
        description="Short explanation (e.g., 'Starlink is a private subsidiary of SpaceX', 'Tata Motors renamed to TMPV')."
    )

structured_llm = llm.with_structured_output(GetSymbol,
            method="function_calling")

@tool
def get_stock_symbol(query: str) -> dict:
    """
    Finds the correct Yahoo Finance stock symbol by searching online first.
    Handles private companies and renames.
    """
    try:
        # 1. Search first to get real-time status (Private vs Public, Renames)
        search_query = f"Is {query} a public company? What is the Yahoo Finance ticker?"
        search_results = search.invoke(search_query)

        # 2. Ask LLM to analyze the search results
        prompt = (
                f"User Query: {query}\n"
                f"Search Results: {search_results}\n\n"
                "Task: Extract the valid Yahoo Finance ticker.\n"
                "1. If multiple listings exist, PREFER THE PRIMARY LISTING (e.g., NSE/BSE for Indian companies) over US OTC (e.g., HYMTF).\n"
                "2. If the company is PRIVATE (e.g., Starlink), return symbol=None.\n"
                "3. If the company was RENAMED (e.g., Tata Motors -> TMPV), use the NEW ticker."
            )

        response = structured_llm.invoke([HumanMessage(content=prompt)])
        
        # 3. Handle the output safely
        if not response.symbol or response.symbol.upper() == "PRIVATE":
            return {"error": f"Cannot fetch price: {response.reason}"}
            
        return {"symbol": response.symbol}

    except Exception as e:
        return {"error": f"Tool error: {str(e)}"}