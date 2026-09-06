#!/usr/bin/env python3
"""
TruthTrace Unified CLI

A single entrypoint for all TruthTrace operations:

  verify     — Verify a news claim against the knowledge base
  ingest     — Fetch and index latest news articles
  status     — Show vector store stats and scheduler state
  sources    — List available news sources

Usage:
  python truthtrace_cli.py verify "Claim text here"
  python truthtrace_cli.py verify "Claim text here" --news-only --top-k 10
  python truthtrace_cli.py ingest --sources rss,factcheck --limit 100
  python truthtrace_cli.py ingest --sources rss --daemon --interval 300
  python truthtrace_cli.py status
  python truthtrace_cli.py sources
"""

import sys
import io
import json
import warnings
import logging
import argparse
from pathlib import Path
from datetime import datetime

# ── Windows: force UTF-8 stdout so emoji/symbols don't crash cp1252 ──────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── Suppress noisy SDK warnings ───────────────────────────────────────────────
warnings.filterwarnings('ignore')
logging.getLogger('google_genai').setLevel(logging.ERROR)
logging.getLogger('huggingface_hub').setLevel(logging.ERROR)
logging.getLogger('sentence_transformers').setLevel(logging.ERROR)

# ── Bootstrap sys.path ────────────────────────────────────────────────────────
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── ANSI colour helpers (no external deps needed) ─────────────────────────────
_RESET   = "\033[0m"
_BOLD    = "\033[1m"
_GREEN   = "\033[92m"
_RED     = "\033[91m"
_YELLOW  = "\033[93m"
_CYAN    = "\033[96m"
_MAGENTA = "\033[95m"
_DIM     = "\033[2m"

def _c(text: str, *codes: str) -> str:
    return "".join(codes) + str(text) + _RESET

def _banner():
    print(_c("""
+----------------------------------------------------------+
|        TruthTrace  -  Real-Time Fact Verification        |
|        RAG + FAISS + Gemini + Multi-Source News          |
+----------------------------------------------------------+
""", _CYAN, _BOLD))


# ── Sub-commands ──────────────────────────────────────────────────────────────

def cmd_verify(args):
    """Verify a claim against the indexed knowledge base."""
    from app.models.schemas import VerificationRequest
    from app.services.verification import verification_service

    claim = " ".join(args.claim)
    print(_c(f"\n[VERIFY]  ", _BOLD) + _c(f'"{claim}"', _CYAN))
    print(_c(f"    news_only={args.news_only}  top_k={args.top_k}\n", _DIM))

    req = VerificationRequest(text=claim, news_only=args.news_only, top_k=args.top_k)
    resp = verification_service.verify(req)

    # Verdict colour
    colours = {
        "TRUE": _GREEN,
        "FALSE": _RED,
        "MISLEADING": _YELLOW,
        "INSUFFICIENT_EVIDENCE": _DIM,
    }
    col = colours.get(resp.verdict.value, _RESET)
    llm_tag = _c(" [Gemini]", _MAGENTA) if getattr(resp, "llm_powered", False) else _c(" [heuristic]", _DIM)

    print(_c(f"  Verdict     : ", _BOLD) + _c(resp.verdict.value, col, _BOLD) + llm_tag)
    print(_c(f"  Confidence  : ", _BOLD) + f"{resp.confidence * 100:.1f}%")
    print(_c(f"  Summary     : ", _BOLD) + resp.summary)
    print(_c(f"  Time        : ", _BOLD) + f"{resp.processing_time_ms:.1f} ms")

    if resp.knowledge_base_freshness:
        print(_c(f"  KB Freshness: ", _BOLD) + resp.knowledge_base_freshness)
    if resp.news_sources_used:
        print(_c(f"  News Sources: ", _BOLD) + str(resp.news_sources_used))

    if resp.reasoning:
        print(_c("\n  Reasoning:", _BOLD))
        for r in resp.reasoning:
            print(f"    - {r}")

    if resp.supporting_evidence:
        print(_c(f"\n  [+] Supporting Evidence ({len(resp.supporting_evidence)}):", _GREEN, _BOLD))
        for ev in resp.supporting_evidence[:3]:
            print(f"    [{ev.reliability_level.value if ev.reliability_level else '?'}] "
                  f"{ev.source} | {ev.publication_date}")
            print(_c(f'      "{ev.text[:120]}..."', _DIM))
            if ev.url:
                print(_c(f"      {ev.url}", _CYAN))

    if resp.contradicting_evidence:
        print(_c(f"\n  [-] Contradicting Evidence ({len(resp.contradicting_evidence)}):", _RED, _BOLD))
        for ev in resp.contradicting_evidence[:3]:
            print(f"    [{ev.reliability_level.value if ev.reliability_level else '?'}] "
                  f"{ev.source} | {ev.publication_date}")
            print(_c(f"      \"{ev.text[:120]}...\"", _DIM))

    if args.json:
        print("\n" + _c("── JSON Output ──", _DIM))
        print(json.dumps(resp.model_dump(), indent=2, default=str))

    print()


def cmd_ingest(args):
    """Fetch and index the latest news articles."""
    import time
    from ingest_pipeline import IngestionOrchestrator

    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    print(_c(f"\n📥  Ingesting from: {sources}  limit={args.limit}\n", _BOLD))

    orchestrator = IngestionOrchestrator(dry_run=args.dry_run)

    try:
        if args.daemon:
            print(_c(f"  Daemon mode — polling every {args.interval}s. Press Ctrl+C to stop.\n", _YELLOW))
            cycle = 1
            while True:
                print(_c(f"\n=== Cycle #{cycle}  [{datetime.now().strftime('%H:%M:%S')}] ===", _CYAN))
                summary = orchestrator.run_cycle(sources=sources, limit_per_cycle=args.limit)
                _print_ingest_summary(summary)
                cycle += 1
                print(_c(f"  Sleeping {args.interval}s…", _DIM))
                time.sleep(args.interval)
        else:
            summary = orchestrator.run_cycle(sources=sources, limit_per_cycle=args.limit)
            _print_ingest_summary(summary)
    except KeyboardInterrupt:
        print(_c("\n  Stopped by user.", _YELLOW))
    finally:
        orchestrator.close()


def _print_ingest_summary(summary: dict):
    print(_c(f"\n  📊  Ingestion Summary", _BOLD))
    print(f"    Raw candidates  : {summary.get('raw_candidates', 0)}")
    print(_c(f"    New indexed     : {summary.get('fresh_indexed_docs', 0)}", _GREEN))
    print(f"    Chunks added    : {summary.get('chunks_added', 0)}")
    print(f"    Store total     : {summary.get('total_store_documents', 0)} docs / "
          f"{summary.get('total_store_chunks', 0)} chunks")
    print(f"    Elapsed         : {summary.get('elapsed_sec', 0):.1f}s")


def cmd_status(args):
    """Display vector store statistics and scheduler state."""
    from app.services.retrieval import vector_store

    stats = vector_store.get_stats()

    print(_c("\n📈  Knowledge Base Status", _BOLD, _CYAN))
    print(f"  Total documents : {stats['total_documents']}")
    print(f"  Total chunks    : {stats['total_chunks']}")
    print(f"  Unique sources  : {stats['unique_sources']}")
    print(f"  Newest article  : {stats.get('newest_article_date') or 'N/A'}")
    print(f"  Oldest article  : {stats.get('oldest_article_date') or 'N/A'}")

    if stats.get("categories"):
        print(_c("\n  Categories:", _BOLD))
        for cat, cnt in sorted(stats["categories"].items(), key=lambda x: -x[1]):
            print(f"    {cat:<20} {cnt:>6} chunks")

    if stats.get("reliability_breakdown"):
        print(_c("\n  Reliability:", _BOLD))
        for lvl, cnt in stats["reliability_breakdown"].items():
            bar = "█" * min(20, cnt // max(1, stats["total_chunks"] // 20))
            print(f"    {lvl:<12} {bar} {cnt}")

    if stats.get("sources") and args.verbose:
        print(_c("\n  Indexed Sources:", _BOLD))
        for src in stats["sources"]:
            print(f"    • {src}")

    print()


def cmd_sources(args):
    """List all available news sources."""
    from ingest_pipeline import CURATED_RSS_FEEDS

    print(_c("\n📰  Available RSS Feeds (no API key required)\n", _BOLD, _CYAN))
    for feed in CURATED_RSS_FEEDS:
        rel = feed.get("reliability", "?")
        cat = feed.get("category", "general")
        print(f"  {_c(feed['name'], _BOLD):<40}  [{cat}]  reliability={rel.value if hasattr(rel,'value') else rel}")

    print(_c("\n🔑  Optional API Sources (configure in backend/.env)\n", _BOLD, _YELLOW))
    print(f"  {'NEWS_API_KEY':<30}  NewsAPI — 50K+ articles/day across all categories")
    print(f"  {'GOOGLE_FACT_CHECK_API_KEY':<30}  Google Fact Check — Snopes, PolitiFact, AFP debunks")
    print()


# ── Argument Parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="truthtrace",
        description="TruthTrace — Real-Time News Verification & Ingestion CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # verify
    p_verify = sub.add_parser("verify", help="Verify a news claim")
    p_verify.add_argument("claim", nargs="+", help="The claim text to verify")
    p_verify.add_argument("--news-only", action="store_true",
                          help="Restrict evidence to news-category chunks only")
    p_verify.add_argument("--top-k", type=int, default=5, metavar="N",
                          help="Evidence chunks per query (1-20, default 5)")
    p_verify.add_argument("--json", action="store_true", help="Also print full JSON response")

    # ingest
    p_ingest = sub.add_parser("ingest", help="Fetch and index latest news articles")
    p_ingest.add_argument("--sources", default="rss",
                          help="Comma-separated: rss, factcheck, newsapi (default: rss)")
    p_ingest.add_argument("--limit", type=int, default=50,
                          help="Max articles per cycle (default: 50)")
    p_ingest.add_argument("--daemon", action="store_true",
                          help="Run continuously in the background")
    p_ingest.add_argument("--interval", type=int, default=300,
                          help="Seconds between daemon cycles (default: 300)")
    p_ingest.add_argument("--dry-run", action="store_true",
                          help="Fetch and deduplicate without writing to vector store")

    # status
    p_status = sub.add_parser("status", help="Show knowledge base statistics")
    p_status.add_argument("--verbose", "-v", action="store_true",
                          help="Show full list of indexed sources")

    # sources
    sub.add_parser("sources", help="List available news source feeds")

    return parser


def main():
    _banner()
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "verify":  cmd_verify,
        "ingest":  cmd_ingest,
        "status":  cmd_status,
        "sources": cmd_sources,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
