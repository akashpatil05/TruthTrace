"""
Multi-source News Ingestion Pipeline for TruthTrace.
Fetches latest news from multiple APIs and RSS feeds.
Automatically indexes them into the FAISS vector store.
"""

import os
import json
import requests
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from abc import ABC, abstractmethod
import feedparser

from app.models.schemas import DocumentIngestRequest, SourceType, ReliabilityLevel
from app.services.preprocessing import preprocessor
from app.services.retrieval import vector_store

# API Keys (set as environment variables)
NEWSAPI_KEY = os.getenv('NEWSAPI_KEY', 'demo')
GUARDIAN_API_KEY = os.getenv('GUARDIAN_API_KEY', 'demo')

class NewsSource(ABC):
    """Abstract base class for news sources."""
    
    @abstractmethod
    def fetch_articles(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch latest articles from the source."""
        pass
    
    @staticmethod
    def hash_article(title: str, source: str) -> str:
        """Generate deterministic hash for article deduplication."""
        text = f"{title}_{source}".lower().strip()
        return hashlib.md5(text.encode()).hexdigest()[:16]


class NewsAPISource(NewsSource):
    """NewsAPI.org integration - covers 50,000+ articles daily."""
    
    def __init__(self):
        self.base_url = 'https://newsapi.org/v2'
        self.api_key = NEWSAPI_KEY
        self.reliability = ReliabilityLevel.HIGH
    
    def fetch_articles(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch from top headlines and search endpoints."""
        articles = []
        
        # Fact-checking and verification related news
        queries = [
            'fact check',
            'misinformation',
            'fake news',
            'verification',
            'debunk',
            'conspiracy theory'
        ]
        
        for query in queries:
            try:
                response = requests.get(
                    f'{self.base_url}/everything',
                    params={
                        'q': query,
                        'sortBy': 'publishedAt',
                        'language': 'en',
                        'apiKey': self.api_key,
                        'pageSize': 5
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for article in data.get('articles', [])[:5]:
                        articles.append({
                            'title': article.get('title', ''),
                            'content': article.get('description', '') or article.get('content', ''),
                            'source': article.get('source', {}).get('name', 'NewsAPI'),
                            'url': article.get('url', ''),
                            'published_at': article.get('publishedAt', ''),
                            'provider': 'NewsAPI'
                        })
                
            except Exception as e:
                print(f'Error fetching from NewsAPI ({query}): {str(e)}')
        
        return articles[:limit]


class RSSFeedSource(NewsSource):
    """RSS Feed integration for news outlets."""
    
    RSS_FEEDS = {
        'BBC News': {
            'url': 'http://feeds.bbc.co.uk/news/rss.xml',
            'reliability': ReliabilityLevel.VERY_HIGH
        },
        'Reuters': {
            'url': 'https://www.reutersagency.com/feed/?feed=topnews',
            'reliability': ReliabilityLevel.VERY_HIGH
        },
        'AP News': {
            'url': 'https://apnews.com/apf-services/v2/factcheck/rss',
            'reliability': ReliabilityLevel.VERY_HIGH
        },
        'NPR': {
            'url': 'https://feeds.npr.org/1001/rss.xml',
            'reliability': ReliabilityLevel.VERY_HIGH
        },
        'The Guardian': {
            'url': 'https://www.theguardian.com/world/rss',
            'reliability': ReliabilityLevel.HIGH
        },
        'Al Jazeera': {
            'url': 'https://www.aljazeera.com/xml/feeds/rss/all.xml',
            'reliability': ReliabilityLevel.HIGH
        },
    }
    
    def fetch_articles(self, limit: int = 20, sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch articles from RSS feeds."""
        articles = []
        
        feeds_to_fetch = sources if sources else list(self.RSS_FEEDS.keys())
        
        for source_name in feeds_to_fetch:
            if source_name not in self.RSS_FEEDS:
                continue
            
            feed_config = self.RSS_FEEDS[source_name]
            try:
                feed = feedparser.parse(feed_config['url'])
                
                for entry in feed.entries[:5]:
                    content = entry.get('summary', '') or entry.get('description', '')
                    articles.append({
                        'title': entry.get('title', ''),
                        'content': content,
                        'source': source_name,
                        'url': entry.get('link', ''),
                        'published_at': entry.get('published', datetime.now().isoformat()),
                        'provider': 'RSS'
                    })
            
            except Exception as e:
                print(f'Error fetching RSS from {source_name}: {str(e)}')
        
        return articles[:limit]


class NewsIngestPipeline:
    """Orchestrates news fetching, processing, and indexing."""
    
    def __init__(self):
        self.newsapi = NewsAPISource()
        self.rss = RSSFeedSource()
        self.ingested_count = 0
        self.skipped_count = 0
        self.seen_articles = self._load_seen_articles()
    
    def _load_seen_articles(self) -> set:
        """Load previously ingested article hashes to avoid duplicates."""
        seen_file = Path(__file__).parent.parent.parent / 'data' / 'processed' / 'ingested_articles.json'
        if seen_file.exists():
            try:
                with open(seen_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return set(data.get('article_hashes', []))
            except Exception:
                pass
        return set()
    
    def _save_seen_articles(self):
        """Persist ingested article hashes."""
        seen_file = Path(__file__).parent.parent.parent / 'data' / 'processed' / 'ingested_articles.json'
        seen_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(seen_file, 'w', encoding='utf-8') as f:
            json.dump({
                'article_hashes': list(self.seen_articles),
                'last_updated': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def process_article(self, article: Dict[str, Any]) -> Optional[DocumentIngestRequest]:
        """Convert raw article to DocumentIngestRequest."""
        
        # Validate article
        if not article.get('title') or not article.get('content'):
            return None
        
        # Check for duplicates
        article_hash = NewsSource.hash_article(article['title'], article['source'])
        if article_hash in self.seen_articles:
            self.skipped_count += 1
            return None
        
        self.seen_articles.add(article_hash)
        
        # Determine reliability based on source
        source_name = article.get('source', 'Unknown')
        reliability = self._get_reliability(source_name, article.get('provider', 'Unknown'))
        source_type = self._get_source_type(source_name)
        
        # Parse publication date
        pub_date = article.get('published_at', datetime.now().isoformat())
        if isinstance(pub_date, str):
            try:
                if 'T' in pub_date:
                    pub_date = pub_date.split('T')[0]
            except Exception:
                pub_date = datetime.now().strftime('%Y-%m-%d')
        
        return DocumentIngestRequest(
            title=article['title'],
            content=article['content'],
            source=source_name,
            url=article.get('url', ''),
            publication_date=pub_date,
            category='news',
            source_type=source_type,
            reliability_level=reliability
        )
    
    def _get_reliability(self, source: str, provider: str) -> ReliabilityLevel:
        """Determine reliability level based on source."""
        very_high_sources = ['BBC', 'Reuters', 'AP', 'NPR', 'Guardian', 'AFP']
        high_sources = ['Al Jazeera', 'CNN', 'NY Times', 'Washington Post']
        
        source_lower = source.lower()
        
        if any(name.lower() in source_lower for name in very_high_sources):
            return ReliabilityLevel.VERY_HIGH
        elif any(name.lower() in source_lower for name in high_sources):
            return ReliabilityLevel.HIGH
        else:
            return ReliabilityLevel.MEDIUM
    
    def _get_source_type(self, source: str) -> SourceType:
        """Determine source type."""
        news_wires = ['Reuters', 'AP', 'AFP']
        mainstream = ['BBC', 'CNN', 'NY Times', 'Guardian', 'Washington Post']
        
        source_lower = source.lower()
        
        if any(name.lower() in source_lower for name in news_wires):
            return SourceType.NEWS_WIRE
        elif any(name.lower() in source_lower for name in mainstream):
            return SourceType.MAINSTREAM_NEWS
        else:
            return SourceType.NEWS_WIRE
    
    def ingest_from_newsapi(self, limit: int = 20) -> int:
        """Fetch and ingest news from NewsAPI."""
        print(f'Fetching articles from NewsAPI...')
        articles = self.newsapi.fetch_articles(limit)
        return self._process_articles(articles)
    
    def ingest_from_rss(self, sources: Optional[List[str]] = None, limit: int = 20) -> int:
        """Fetch and ingest news from RSS feeds."""
        print(f'Fetching articles from RSS feeds...')
        articles = self.rss.fetch_articles(limit, sources)
        return self._process_articles(articles)
    
    def ingest_all_sources(self, limit_per_source: int = 15) -> Dict[str, int]:
        """Fetch from all available sources."""
        print('Starting multi-source news ingestion pipeline...\n')
        
        results = {
            'newsapi': self.ingest_from_newsapi(limit_per_source),
            'rss': self.ingest_from_rss(limit=limit_per_source)
        }
        
        self._save_seen_articles()
        
        print(f'\n✓ Ingestion complete!')
        print(f'  Total ingested: {self.ingested_count}')
        print(f'  Total skipped (duplicates): {self.skipped_count}')
        
        return results
    
    def _process_articles(self, articles: List[Dict[str, Any]]) -> int:
        """Process list of articles and ingest into vector store."""
        count = 0
        for article in articles:
            doc_req = self.process_article(article)
            if doc_req:
                try:
                    doc_res = preprocessor.process_document(doc_req)
                    chunks_added = vector_store.ingest_document(doc_res)
                    if chunks_added > 0:
                        count += 1
                        print(f'✓ Ingested: {article["title"][:60]}...')
                except Exception as e:
                    print(f'✗ Failed to ingest {article.get("title", "Unknown")}: {str(e)}')
        
        self.ingested_count += count
        return count


def main():
    """Main entry point for news ingestion."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest latest news into TruthTrace')
    parser.add_argument('--source', choices=['all', 'newsapi', 'rss'], default='all',
                        help='News source to ingest from')
    parser.add_argument('--limit', type=int, default=15,
                        help='Number of articles per source')
    parser.add_argument('--rss-sources', nargs='+', 
                        help='Specific RSS sources to fetch from')
    
    args = parser.parse_args()
    
    pipeline = NewsIngestPipeline()
    
    if args.source == 'all':
        pipeline.ingest_all_sources(args.limit)
    elif args.source == 'newsapi':
        pipeline.ingest_from_newsapi(args.limit)
    elif args.source == 'rss':
        pipeline.ingest_from_rss(args.rss_sources, args.limit)
    
    print(f'\nVector Store Status:')
    print(f'  Total chunks: {vector_store.count()}')
    print(f'  Total documents: {len(vector_store.list_documents())}')


if __name__ == '__main__':
    main()
