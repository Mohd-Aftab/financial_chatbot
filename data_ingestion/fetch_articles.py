import os
from dotenv import load_dotenv
import requests

load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

def fetch_company_news(company: str, api_key: str, days: int = 30):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": company,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": 20,
        "apiKey": api_key
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()["articles"]