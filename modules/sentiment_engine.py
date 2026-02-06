
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import time
import asyncio
from datetime import datetime

class SentimentEngine:
    """
    The Ears of IronClad.
    Fetches news via RSS and scores sentiment using VADER.
    """
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        self.scores = {} # Dictionary to store {ticker: score}
        self.last_updated = {} # {ticker: timestamp}
        self.cache_validity = 3600 # 1 hour cache
        
    def fetch_news(self, ticker: str):
        """
        Fetches news headlines from Google News RSS.
        """
        # Clean ticker for search (e.g., "TCS.NS" -> "TCS share price India")
        search_term = f"{ticker.split('.')[0]} share price news India"
        encoded_term = search_term.replace(" ", "%20")
        url = f"https://news.google.com/rss/search?q={encoded_term}&hl=en-IN&gl=IN&ceid=IN:en"
        
        try:
            feed = feedparser.parse(url)
            headlines = []
            for entry in feed.entries[:5]: # Top 5 news only
                headlines.append(entry.title)
            return headlines
        except Exception as e:
            print(f"[{ticker}] Error fetching news: {e}")
            return []

    def get_sentiment(self, ticker: str):
        """
        Returns the cached sentiment score for a ticker.
        Score range: -1.0 (Very Negative) to 1.0 (Very Positive).
        """
        # Return cached if valid
        if ticker in self.scores:
            if time.time() - self.last_updated.get(ticker, 0) < self.cache_validity:
                return self.scores[ticker]
        
        # Else fetch fresh
        headlines = self.fetch_news(ticker)
        if not headlines:
            return 0.0 # Neutral if no news
            
        compound_scores = []
        for h in headlines:
            vs = self.analyzer.polarity_scores(h)
            compound_scores.append(vs['compound'])
            
        if not compound_scores:
            avg_score = 0.0
        else:
            avg_score = sum(compound_scores) / len(compound_scores)
            
        # Update Cache
        self.scores[ticker] = avg_score
        self.last_updated[ticker] = time.time()
        
        # print(f"[{ticker}] Sentiment Updated: {avg_score:.2f} ({len(headlines)} headlines)")
        return avg_score

# Async wrapper for background loop
async def run_sentiment_scanner(sentiment_engine, tickers):
    """
    Background loop to update sentiment every hour.
    """
    loop = asyncio.get_running_loop()
    while True:
        print(f"[{datetime.now()}] 👂 Scanning News Sentiment...")
        for ticker in tickers:
            # We don't want to spam requests, so small delay
            # Run blocking call in thread pool
            await loop.run_in_executor(None, sentiment_engine.get_sentiment, ticker)
            await asyncio.sleep(2) # 2 seconds between requests
            
        await asyncio.sleep(3600) # Sleep for 1 hour
