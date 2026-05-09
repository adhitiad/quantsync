import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

class RSSScraper:
    def __init__(self):
        self.feeds = {
            "reddit_crypto": "https://www.reddit.com/r/CryptoCurrency/.rss",
            "reddit_forex": "https://www.reddit.com/r/forex/.rss",
            "cnbc": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
            "detik_finance": "https://finance.detik.com/rss",
            "kompas_money": "https://money.kompas.com/rss/money.xml",
            "google_finance": "https://news.google.com/rss/search?q=finance&hl=en-US&gl=US&ceid=US:en"
        }

    def fetch_feed(self, name, url):
        print(f"Fetching RSS feed: {name}...")
        try:
            # Some RSS feeds (like Reddit) require a User-Agent
            feed = feedparser.parse(url, agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Trading-Hub/1.0')
            entries = []
            for entry in feed.entries:
                entries.append({
                    "source": name,
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": self._clean_html(entry.get("summary", entry.get("description", ""))),
                    "published": entry.get("published", datetime.now().isoformat()),
                    "timestamp": time.time()
                })
            return entries
        except Exception as e:
            print(f"Error fetching {name}: {e}")
            return []

    def _clean_html(self, html):
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text()

    def scrape_all(self):
        all_data = []
        for name, url in self.feeds.items():
            all_data.extend(self.fetch_feed(name, url))
        return all_data

if __name__ == "__main__":
    scraper = RSSScraper()
    results = scraper.scrape_all()
    print(f"Total items scraped: {len(results)}")
