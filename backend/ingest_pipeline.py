#!/usr/bin/env python3
"""
TruthTrace Live Real-Time Data Ingestion Pipeline.

Streams, deduplicates, and indexes real-time news articles, scientific reports,
and fact-checking debunks from multiple live feeds:
1. Curated Authoritative RSS Feeds (BBC, ScienceDaily, WHO, NASA, The Guardian) - No API Key Required
2. Google Fact Check Tools API (Snopes, PolitiFact, FactCheck.org debunks) - Optional API Key
3. NewsAPI (Top Global & Categorical Headlines) - Optional API Key

Usage:
    # Run once to ingest up to 50 latest articles from RSS feeds:
    python ingest_pipeline.py --sources rss --limit 50

    # Stream continuously every 5 minutes:
    python ingest_pipeline.py --sources rss --limit 100 --daemon --interval 300

    # Include NewsAPI and Google Fact Check (if keys configured in .env):
    python ingest_pipeline.py --sources rss,factcheck,newsapi --limit 200
"""

import os
import sys
import json
import time
import re
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

# Add backend root to path to allow importing app modules
BACKEND_DIR = Path(__file__).resolve().parent
sys.stdout.reconfigure(line_buffering=True)

from app.config import settings, BASE_DIR
from app.models.schemas import (
    DocumentIngestRequest,
    SourceType,
    ReliabilityLevel,
)
from app.services.preprocessing import preprocessor
from app.services.retrieval import vector_store

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("TruthTraceIngestion")

# Cache file for tracked URLs to avoid duplicate processing
SEEN_URLS_FILE = BASE_DIR.parent / "data" / "processed" / "seen_urls.json"


# ==============================================================================
# 1. URL Deduplication Tracker
# ==============================================================================

class URLTracker:
    """Maintains a persistent registry of indexed URLs to ensure idempotent ingestion."""

    def __init__(self, cache_file: Path = SEEN_URLS_FILE):
        self.cache_file = cache_file
        self.seen_urls: Set[str] = self._load()

        # Also populate with already indexed URLs from FAISS
        try:
            indexed_docs = vector_store.list_documents()
            for doc in indexed_docs:
                url = doc.get("url")
                if url:
                    self.seen_urls.add(url.strip().lower())
        except Exception as e:
            logger.debug(f"Could not load existing vector store URLs: {e}")

    def _load(self) -> Set[str]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(u.strip().lower() for u in data if isinstance(u, str))
            except Exception as e:
                logger.warning(f"Error loading seen URLs cache: {e}")
        return set()

    def save(self):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(sorted(list(self.seen_urls)), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save seen URLs cache: {e}")

    def is_seen(self, url: str) -> bool:
        if not url:
            return True
        clean = url.strip().lower()
        return clean in self.seen_urls

    def mark_seen(self, url: str):
        if url:
            self.seen_urls.add(url.strip().lower())


# ==============================================================================
# 2. RSS Feed Collector (Zero External Dependencies & No API Key Needed)
# ==============================================================================

CURATED_RSS_FEEDS = [
    {
        "name": "BBC News - World",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "international",
        "source_type": SourceType.NEWS_WIRE,
        "reliability": ReliabilityLevel.HIGH,
    },
    {
        "name": "BBC News - Science & Environment",
        "url": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "category": "science",
        "source_type": SourceType.NEWS_WIRE,
        "reliability": ReliabilityLevel.HIGH,
    },
    {
        "name": "BBC News - Health",
        "url": "http://feeds.bbci.co.uk/news/health/rss.xml",
        "category": "health",
        "source_type": SourceType.NEWS_WIRE,
        "reliability": ReliabilityLevel.HIGH,
    },
    {
        "name": "ScienceDaily - Top Science News",
        "url": "https://www.sciencedaily.com/rss/top/science.xml",
        "category": "science",
        "source_type": SourceType.PEER_REVIEWED_JOURNAL,
        "reliability": ReliabilityLevel.VERY_HIGH,
    },
    {
        "name": "ScienceDaily - Health & Medicine",
        "url": "https://www.sciencedaily.com/rss/health_medicine.xml",
        "category": "health",
        "source_type": SourceType.PEER_REVIEWED_JOURNAL,
        "reliability": ReliabilityLevel.VERY_HIGH,
    },
    {
        "name": "NASA - Breaking News",
        "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "category": "science",
        "source_type": SourceType.GOVERNMENT_AGENCY,
        "reliability": ReliabilityLevel.VERY_HIGH,
    },
    {
        "name": "The Guardian - World News",
        "url": "https://www.theguardian.com/world/rss",
        "category": "international",
        "source_type": SourceType.MAINSTREAM_NEWS,
        "reliability": ReliabilityLevel.HIGH,
    },
]


def find_elem(parent: ET.Element, *tags: str) -> Optional[ET.Element]:
    """Safely find first matching element without triggering boolean evaluation of Element."""
    for tag in tags:
        elem = parent.find(tag)
        if elem is not None:
            return elem
    return None


def clean_xml_text(elem: Optional[ET.Element]) -> str:
    """Extract and sanitize text from an XML element, stripping HTML tags."""
    if elem is None or elem.text is None:
        return ""
    text = elem.text.strip()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class RSSFeedCollector:
    """Collects real-time articles from curated RSS feeds."""

    def __init__(self, client: httpx.Client, feeds: List[Dict[str, Any]] = None):
        self.client = client
        self.feeds = feeds or CURATED_RSS_FEEDS

    def fetch_feed(self, feed_meta: Dict[str, Any]) -> List[DocumentIngestRequest]:
        feed_name = feed_meta["name"]
        url = feed_meta["url"]
        articles: List[DocumentIngestRequest] = []

        try:
            resp = self.client.get(
                url,
                headers={"User-Agent": "TruthTrace-FeedBot/1.0 (+http://127.0.0.1:5173)"},
                timeout=12.0,
            )
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch RSS {feed_name}: HTTP {resp.status_code}")
                return []

            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            if not items:
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in items:
                title_elem = find_elem(item, "title", "{http://www.w3.org/2005/Atom}title")
                title = clean_xml_text(title_elem)

                link_elem = find_elem(item, "link", "{http://www.w3.org/2005/Atom}link")
                link = ""
                if link_elem is not None:
                    link = (link_elem.text or link_elem.attrib.get("href") or "").strip()

                desc_elem = find_elem(
                    item,
                    "description",
                    "{http://www.w3.org/2005/Atom}summary",
                    "{http://www.w3.org/2005/Atom}content",
                )
                desc = clean_xml_text(desc_elem)

                pub_elem = find_elem(
                    item,
                    "pubDate",
                    "{http://www.w3.org/2005/Atom}published",
                    "{http://www.w3.org/2005/Atom}updated",
                )
                pub_date_raw = clean_xml_text(pub_elem)

                from datetime import timezone
                pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if pub_date_raw:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date_raw)
                        pub_date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                content = f"{title}\n\n{desc}" if desc and desc != title else title

                if title and link:
                    req = DocumentIngestRequest(
                        title=title,
                        content=content,
                        source=feed_name,
                        url=link,
                        publication_date=pub_date,
                        category=feed_meta["category"],
                        source_type=feed_meta["source_type"],
                        reliability_level=feed_meta["reliability"],
                    )
                    articles.append(req)

        except Exception as e:
            logger.error(f"Error parsing RSS feed '{feed_name}' ({url}): {e}")

        return articles

    def collect(self, limit: int = 100) -> List[DocumentIngestRequest]:
        all_docs: List[DocumentIngestRequest] = []
        for feed in self.feeds:
            if len(all_docs) >= limit:
                break
            logger.info(f"Checking RSS Feed: {feed['name']}...")
            docs = self.fetch_feed(feed)
            all_docs.extend(docs)
            logger.info(f"  -> Extracted {len(docs)} items from {feed['name']}")
        return all_docs[:limit]


# ==============================================================================
# 3. Google Fact Check Tools API Collector (Optional API Key)
# ==============================================================================

class GoogleFactCheckCollector:
    """Fetches verified fact-checks from Snopes, PolitiFact, and AFP via Google Fact Check API."""

    BASE_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    def __init__(self, client: httpx.Client, api_key: Optional[str] = None):
        self.client = client
        self.api_key = api_key or os.getenv("GOOGLE_FACT_CHECK_API_KEY")

    def collect(self, queries: List[str] = None, limit: int = 50) -> List[DocumentIngestRequest]:
        if not self.api_key:
            logger.info("Google Fact Check API Key not configured; skipping Fact Check Tools API.")
            return []

        search_topics = queries or ["vaccine", "climate", "cancer", "election", "artificial intelligence"]
        docs: List[DocumentIngestRequest] = []

        for topic in search_topics:
            if len(docs) >= limit:
                break
            try:
                params = {
                    "query": topic,
                    "languageCode": "en",
                    "pageSize": 20,
                    "key": self.api_key,
                }
                resp = self.client.get(self.BASE_URL, params=params, timeout=10.0)
                if resp.status_code != 200:
                    logger.warning(f"Google Fact Check query '{topic}' returned HTTP {resp.status_code}")
                    continue

                data = resp.json()
                claims = data.get("claims", [])

                for item in claims:
                    claim_text = item.get("text", "")
                    claim_reviews = item.get("claimReview", [])
                    if not claim_reviews:
                        continue

                    review = claim_reviews[0]
                    publisher = review.get("publisher", {}).get("name", "Fact Checker")
                    review_url = review.get("url", "")
                    review_title = review.get("title") or f"Fact Check: {claim_text[:80]}"
                    rating = review.get("textualRating", "Evaluated")
                    review_date = review.get("reviewDate", datetime.utcnow().strftime("%Y-%m-%d"))[:10]

                    body = (
                        f"Claim evaluated: {claim_text}\n"
                        f"Fact-checking verdict by {publisher}: {rating}.\n"
                        f"Review title: {review_title}."
                    )

                    req = DocumentIngestRequest(
                        title=f"[{rating.upper()}] {claim_text}",
                        content=body,
                        source=f"{publisher} (Fact-Check)",
                        url=review_url,
                        publication_date=review_date,
                        category="fact_check",
                        source_type=SourceType.FACT_CHECKER,
                        reliability_level=ReliabilityLevel.VERY_HIGH,
                    )
                    docs.append(req)

            except Exception as e:
                logger.error(f"Error querying Google Fact Check API for '{topic}': {e}")

        return docs[:limit]


# ==============================================================================
# 4. NewsAPI Collector (Optional API Key)
# ==============================================================================

class NewsAPICollector:
    """Collects breaking articles from NewsAPI across categories."""

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, client: httpx.Client, api_key: Optional[str] = None):
        self.client = client
        self.api_key = api_key or os.getenv("NEWS_API_KEY")

    def collect(self, categories: List[str] = None, limit: int = 50) -> List[DocumentIngestRequest]:
        if not self.api_key:
            logger.info("NewsAPI key not configured; skipping NewsAPI stream.")
            return []

        cats = categories or ["general", "science", "health", "technology"]
        docs: List[DocumentIngestRequest] = []

        for cat in cats:
            if len(docs) >= limit:
                break
            try:
                params = {
                    "category": cat,
                    "language": "en",
                    "pageSize": 40,
                    "apiKey": self.api_key,
                }
                resp = self.client.get(self.BASE_URL, params=params, timeout=10.0)
                if resp.status_code != 200:
                    logger.warning(f"NewsAPI query '{cat}' returned HTTP {resp.status_code}")
                    continue

                data = resp.json()
                articles = data.get("articles", [])

                for art in articles:
                    title = art.get("title") or ""
                    url = art.get("url") or ""
                    desc = art.get("description") or ""
                    content = art.get("content") or desc
                    source_name = art.get("source", {}).get("name", "NewsAPI")
                    published = (art.get("publishedAt") or datetime.utcnow().strftime("%Y-%m-%d"))[:10]

                    if "[Removed]" in title or not url or len(title) < 10:
                        continue

                    full_content = f"{title}\n\n{desc}\n\n{content}"

                    req = DocumentIngestRequest(
                        title=title,
                        content=full_content,
                        source=source_name,
                        url=url,
                        publication_date=published,
                        category=cat,
                        source_type=SourceType.MAINSTREAM_NEWS,
                        reliability_level=ReliabilityLevel.HIGH,
                    )
                    docs.append(req)

            except Exception as e:
                logger.error(f"Error querying NewsAPI for category '{cat}': {e}")

        return docs[:limit]


# ==============================================================================
# 5. Ingestion Orchestrator & Indexer
# ==============================================================================

class IngestionOrchestrator:
    """Manages collection, deduplication, chunking, and FAISS indexing."""

    def __init__(self, api_url: Optional[str] = None, dry_run: bool = False):
        self.api_url = api_url
        self.dry_run = dry_run
        self.tracker = URLTracker()
        self.client = httpx.Client(follow_redirects=True, timeout=15.0)

    def close(self):
        self.client.close()

    def run_cycle(self, sources: List[str], limit_per_cycle: int = 100) -> Dict[str, Any]:
        """Execute a single ingestion run."""
        start_time = time.time()
        logger.info(f"--- Starting Ingestion Cycle (Sources: {sources}, Limit: {limit_per_cycle}) ---")

        candidates: List[DocumentIngestRequest] = []

        if "rss" in sources:
            rss_collector = RSSFeedCollector(self.client)
            candidates.extend(rss_collector.collect(limit=limit_per_cycle))

        if "factcheck" in sources:
            fact_collector = GoogleFactCheckCollector(self.client)
            candidates.extend(fact_collector.collect(limit=limit_per_cycle // 2))

        if "newsapi" in sources:
            news_collector = NewsAPICollector(self.client)
            candidates.extend(news_collector.collect(limit=limit_per_cycle // 2))

        logger.info(f"Total collected raw candidates: {len(candidates)}")

        # Deduplicate
        fresh_docs: List[DocumentIngestRequest] = []
        for doc in candidates:
            if not self.tracker.is_seen(doc.url):
                fresh_docs.append(doc)
            if len(fresh_docs) >= limit_per_cycle:
                break

        logger.info(f"Fresh new documents to index after deduplication: {len(fresh_docs)}")

        indexed_docs_count = 0
        total_chunks_added = 0

        for i, doc_req in enumerate(fresh_docs, start=1):
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would index ({i}/{len(fresh_docs)}): '{doc_req.title}' from {doc_req.source}")
                indexed_docs_count += 1
                continue

            try:
                if self.api_url:
                    resp = self.client.post(self.api_url, json=doc_req.model_dump(mode="json"))
                    if resp.status_code == 201:
                        data = resp.json()
                        chunks_added = data.get("num_chunks", 1)
                        total_chunks_added += chunks_added
                        indexed_docs_count += 1
                        self.tracker.mark_seen(doc_req.url)
                        logger.info(f"[{i}/{len(fresh_docs)}] (HTTP) Indexed {chunks_added} chunks: {doc_req.title[:60]}")
                    else:
                        logger.warning(f"HTTP Ingestion failed for {doc_req.url}: {resp.status_code} {resp.text}")
                else:
                    doc_res = preprocessor.process_document(doc_req)
                    chunks_added = vector_store.ingest_document(doc_res)
                    total_chunks_added += chunks_added
                    indexed_docs_count += 1
                    self.tracker.mark_seen(doc_req.url)
                    logger.info(f"[{i}/{len(fresh_docs)}] Indexed {chunks_added} chunks: {doc_req.title[:60]}")

            except Exception as e:
                logger.error(f"Failed to process/index document '{doc_req.title}': {e}")

        if not self.dry_run:
            self.tracker.save()

        elapsed = round(time.time() - start_time, 2)
        summary = {
            "elapsed_sec": elapsed,
            "raw_candidates": len(candidates),
            "fresh_indexed_docs": indexed_docs_count,
            "chunks_added": total_chunks_added,
            "total_store_documents": len(vector_store.list_documents()),
            "total_store_chunks": vector_store.count(),
        }

        logger.info(f"--- Ingestion Cycle Completed in {elapsed}s ---")
        logger.info(f"New docs indexed: {indexed_docs_count} | Chunks added: {total_chunks_added}")
        logger.info(f"Vector Store Total: {summary['total_store_documents']} documents, {summary['total_store_chunks']} chunks.")

        return summary


# ==============================================================================
# 6. CLI Entrypoint
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="TruthTrace Real-Time Ingestion Pipeline")
    parser.add_argument(
        "--sources",
        type=str,
        default="rss",
        help="Comma-separated list of sources to query: rss, factcheck, newsapi (default: rss)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of fresh documents to ingest per cycle (default: 50)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=None,
        help="Optional URL of running backend API endpoint (e.g., http://127.0.0.1:8001/api/documents)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and deduplicate without saving to vector store",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously in background mode with periodic interval",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Interval in seconds between ingestion runs when in daemon mode (default: 300)",
    )

    args = parser.parse_args()
    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]

    orchestrator = IngestionOrchestrator(api_url=args.api_url, dry_run=args.dry_run)

    try:
        if args.daemon:
            logger.info(f"Starting Ingestion Pipeline Daemon (polling every {args.interval}s)...")
            cycle = 1
            while True:
                logger.info(f"\n=== Daemon Polling Cycle #{cycle} ===")
                orchestrator.run_cycle(sources=sources, limit_per_cycle=args.limit)
                cycle += 1
                logger.info(f"Sleeping for {args.interval} seconds...")
                time.sleep(args.interval)
        else:
            orchestrator.run_cycle(sources=sources, limit_per_cycle=args.limit)

    except KeyboardInterrupt:
        logger.info("Ingestion pipeline stopped by user.")
    finally:
        orchestrator.close()


if __name__ == "__main__":
    main()
