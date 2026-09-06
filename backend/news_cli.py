#!/usr/bin/env python
"""
CLI tool to manually ingest latest news into TruthTrace.

Usage:
    python news_cli.py --help
    python news_cli.py --source all --limit 20
    python news_cli.py --source rss --rss-sources "BBC News" "Reuters"
    python news_cli.py --source newsapi --limit 10
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from news_ingestion import NewsIngestPipeline, RSSFeedSource


def print_welcome():
    print("""
╔════════════════════════════════════════════════════════════════╗
║        TRUTHTRACE NEWS INGESTION CLI                           ║
║        Fetch and index latest news into knowledge base         ║
╚════════════════════════════════════════════════════════════════╝
    """)


def list_available_sources():
    """Display available RSS sources."""
    print('\n📰 Available RSS Sources:')
    print('─' * 60)
    for source_name, config in RSSFeedSource.RSS_FEEDS.items():
        reliability = config['reliability'].value
        print(f'  • {source_name:<20} (Reliability: {reliability})')
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Ingest latest news into TruthTrace knowledge base',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch from all sources
  python news_cli.py --source all --limit 20
  
  # Fetch only from RSS feeds
  python news_cli.py --source rss --limit 15
  
  # Fetch from specific RSS sources
  python news_cli.py --source rss --rss-sources "BBC News" "Reuters"
  
  # Fetch from NewsAPI
  python news_cli.py --source newsapi --limit 10
  
  # List available sources
  python news_cli.py --list-sources
        """
    )
    
    parser.add_argument(
        '--source',
        choices=['all', 'newsapi', 'rss'],
        default='all',
        help='News source to ingest from (default: all)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=15,
        help='Number of articles per source (default: 15)'
    )
    
    parser.add_argument(
        '--rss-sources',
        nargs='+',
        help='Specific RSS sources to fetch from (use --list-sources to see all)'
    )
    
    parser.add_argument(
        '--list-sources',
        action='store_true',
        help='List all available RSS sources'
    )
    
    args = parser.parse_args()
    
    print_welcome()
    
    if args.list_sources:
        list_available_sources()
        return
    
    print(f'Configuration:')
    print(f'  Source: {args.source}')
    print(f'  Limit per source: {args.limit}')
    if args.rss_sources:
        print(f'  RSS Sources: {", ".join(args.rss_sources)}')
    print()
    
    pipeline = NewsIngestPipeline()
    
    if args.source == 'all':
        print('📥 Ingesting from all sources...\n')
        results = pipeline.ingest_all_sources(args.limit)
        
        print(f'\n📊 Results:')
        print(f'  NewsAPI: {results.get("newsapi", 0)} articles ingested')
        print(f'  RSS: {results.get("rss", 0)} articles ingested')
    
    elif args.source == 'newsapi':
        print('📥 Ingesting from NewsAPI...\n')
        count = pipeline.ingest_from_newsapi(args.limit)
        print(f'\n✓ Ingested {count} articles from NewsAPI')
    
    elif args.source == 'rss':
        print('📥 Ingesting from RSS feeds...\n')
        count = pipeline.ingest_from_rss(args.rss_sources, args.limit)
        print(f'\n✓ Ingested {count} articles from RSS')
    
    # Final status
    from app.services.retrieval import vector_store
    print(f'\n📈 Vector Store Status:')
    print(f'  Total indexed chunks: {vector_store.count()}')
    print(f'  Total documents: {len(vector_store.list_documents())}')
    print(f'  Latest news indexed: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    
    print('\n✅ News ingestion complete!')


if __name__ == '__main__':
    from datetime import datetime
    main()
