from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

llm = ChatOpenAI()

class CompanyIdentity(BaseModel):
    canonical_name: str = Field(
        description="Official company name used in filings and media"
    )
    ticker: str = Field(
        description="Official stock ticker (Yahoo Finance compatible)"
    )
    exchange: str = Field(
        description="Stock exchange, e.g. NASDAQ, NSE, NYSE"
    )

structured_llm = llm.with_structured_output(
    CompanyIdentity,
    method="function_calling"
)

def resolve_company_identity(query: str) -> dict:
    """
    Resolve a user-provided company name into a canonical company name
    and official stock ticker suitable for news ingestion and vector storage.
    """
    response = structured_llm.invoke([HumanMessage(content=query)])

    return response.dict()
