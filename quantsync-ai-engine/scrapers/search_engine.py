from ddgs import DDGS
from datetime import datetime
import time
import logging

logger = logging.getLogger(__name__)

class SearchEngine:
    def __init__(self):
        self._last_search = {}
        self._cache_duration = 3600  # 1 hour cache

    def search_sentiment(self, asset_name):
        now = datetime.now().timestamp()
        if asset_name in self._last_search:
            if now - self._last_search[asset_name]["time"] < self._cache_duration:
                logger.info(f"Using cached sentiment for {asset_name}")
                return self._last_search[asset_name]["results"]

        logger.info(f"🔍 [Search] Searching DuckDuckGo for {asset_name} sentiment...")
        results = []
        
        # Retry logic for network instability
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # DDGS can be sensitive to rapid requests
                with DDGS(timeout=20) as ddgs:
                    query = f"{asset_name} crypto market sentiment analysis news"
                    search_results = list(ddgs.news(query, max_results=5))
                    
                    for r in search_results:
                        results.append({
                            "source": "duckduckgo",
                            "title": r.get("title", ""),
                            "link": r.get("url", ""),
                            "summary": r.get("body", ""),
                            "published": r.get("date", datetime.now().isoformat()),
                            "timestamp": now
                        })
                    
                    if results:
                        self._last_search[asset_name] = {
                            "time": now,
                            "results": results
                        }
                        return results
                    
            except Exception as e:
                logger.warning(f"⚠️ [Search] Attempt {attempt+1} failed for {asset_name}: {e}")
                if "403" in str(e):
                    break # Don't retry on 403
                time.sleep(2) # Wait before retry
                
        return results
