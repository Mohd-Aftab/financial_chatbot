import requests
from bs4 import BeautifulSoup

def fetch_full_article(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            }
        )

        # Raise HTTPError for 4xx/5xx
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        paragraphs = soup.find_all("p")
        if not paragraphs:
            return ""

        text = " ".join(p.get_text(strip=True) for p in paragraphs)

        return text.strip()

    except requests.exceptions.Timeout:
        print(f"Timeout while fetching article: {url}")
        return ""

    except requests.exceptions.RequestException as e:
        # Covers ConnectionError, HTTPError, TooManyRedirects, etc.
        print(f"Request error for {url}: {e}")
        return ""

    except Exception as e:
        # Safety net (HTML parsing, encoding issues, etc.)
        print(f"Unexpected error for {url}: {e}")
        return ""
