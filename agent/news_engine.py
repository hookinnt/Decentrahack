import requests
import xml.etree.ElementTree as ET
from typing import List, Dict

class NewsEngine:
    """
    Professional news fetcher that pulls real-time crypto events 
    to provide the AI with a diverse stream of threat vectors.
    """
    RSS_FEEDS = [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/"
    ]

    def __init__(self):
        self.seen_guids = set()

    def fetch_latest_news(self) -> List[Dict[str, str]]:
        """Fetches the latest items from RSS feeds."""
        feed_items = []
        for url in self.RSS_FEEDS:
            try:
                response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code != 200: continue
                
                root = ET.fromstring(response.content)
                for item in root.findall('.//item'):
                    title = item.find('title').text
                    link = item.find('link').text
                    description = item.find('description').text if item.find('description') is not None else ""
                    guid = item.find('guid').text if item.find('guid') is not None else link
                    
                    if guid not in self.seen_guids:
                        feed_items.append({
                            "id": guid,
                            "headline": title[:100],
                            "content": f"{title}. {description}"[:500]
                        })
                        self.seen_guids.add(guid)
            except Exception as e:
                print(f"[NEWS ENGINE ERROR] Failed to fetch {url}: {e}")
        
        return feed_items
