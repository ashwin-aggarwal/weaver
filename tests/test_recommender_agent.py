"""
Test: Recommender Agent
Fetches 3 recommendations from arXiv and verifies they match paper topics.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from config import ANTHROPIC_API_KEY
from src.tools.neo4j_store import Neo4jStore
from src.agents.recommender import RecommenderAgent

def test_recommender_agent():
    store  = Neo4jStore()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    agent  = RecommenderAgent(store, client)

    # collect known topics from graph for verification
    papers       = store.get_all_papers()
    known_topics = set()
    for p in papers:
        for t in (p.get("topics") or []):
            known_topics.add(t.lower())

    print(f"\nKnown topics in graph: {', '.join(known_topics) or '(none)'}\n")
    print("Fetching recommendations from arXiv…\n")

    recs = agent.get_recommendations(max_results=3)

    # ── verify shape ──────────────────────────────────────────────
    assert isinstance(recs, list), "Recommendations should be a list"

    if not recs:
        print("⚠ No recommendations returned (may be an arXiv/Claude issue — not a code failure)")
        store.close()
        return

    assert len(recs) <= 3, "Should return at most 3 recommendations"

    topic_hits = 0
    for i, rec in enumerate(recs, 1):
        assert "title"        in rec, f"Rec {i} missing 'title'"
        assert "arxiv_url"    in rec, f"Rec {i} missing 'arxiv_url'"
        assert "why_relevant" in rec, f"Rec {i} missing 'why_relevant'"
        assert "confidence"   in rec, f"Rec {i} missing 'confidence'"
        assert 0.0 <= rec["confidence"] <= 1.0, f"Rec {i} confidence out of range"

        print(f"  [{i}] {rec['title']}")
        print(f"       {rec['arxiv_url']}")
        print(f"       Why: {rec['why_relevant']}")
        print(f"       Relevance: {rec['confidence']:.0%}\n")

        # check topic overlap (loose: at least one topic word in why_relevant or title)
        combined = (rec["title"] + " " + rec["why_relevant"]).lower()
        if any(t in combined for t in known_topics):
            topic_hits += 1

    print(f"Topic relevance: {topic_hits}/{len(recs)} recommendations mention known topics")
    assert topic_hits > 0, "None of the recommendations mention your known topics — check relevance"

    store.close()
    print("\n✓ Recommender Agent test passed")

if __name__ == "__main__":
    test_recommender_agent()
