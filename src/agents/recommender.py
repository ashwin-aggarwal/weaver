"""
Recommender Agent

Queries your knowledge graph for topics, searches arXiv for new papers,
has Claude rank them by relevance, and stores top recommendations in Neo4j.
Supports thumbs-up / thumbs-down feedback.
"""

import json
import re
import time
from datetime import datetime, timezone

import anthropic
import arxiv

SYSTEM_PROMPT = """You are a research recommendation engine.
Given a researcher's existing papers and topics, rank candidate papers by relevance.
Respond ONLY with valid JSON — no explanation, no markdown fences."""

RANKING_PROMPT = """The researcher studies the following topics:
{topics}

Their existing papers:
{existing}

Candidate papers from arXiv:
{candidates}

For each candidate, decide if it is strongly relevant to the researcher's work.
Return ONLY the top 3 most relevant as a JSON array:
[
  {{
    "arxiv_id":     "<arXiv paper id>",
    "title":        "<title>",
    "arxiv_url":    "<https://arxiv.org/abs/id>",
    "why_relevant": "<one sentence: what specific connection to their work>",
    "confidence":   <float 0.0-1.0>
  }},
  ...
]

Return [] if no candidates are strongly relevant (confidence < 0.7).
"""


def _parse_json(raw: str) -> list:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    # Find the start of the JSON array and decode only that, ignoring trailing text
    start = raw.find("[")
    if start == -1:
        return []
    value, _ = json.JSONDecoder().raw_decode(raw, start)
    return value


class RecommenderAgent:
    def __init__(self, neo4j_store, client: anthropic.Anthropic):
        self.store  = neo4j_store
        self.client = client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_recommendations(self, max_results: int = 3) -> list[dict]:
        """
        Find and return up to max_results new paper recommendations.

        Each recommendation dict:
            {arxiv_id, title, arxiv_url, why_relevant, confidence, timestamp}

        Also stores them in Neo4j as Recommendation nodes.
        """
        papers = self.store.get_all_papers()
        if not papers:
            print("No papers in graph — ingest some papers first.")
            return []

        topics   = self._collect_topics(papers)
        existing = self._fmt_existing(papers)

        candidates = self._search_arxiv(topics)
        if not candidates:
            print("No arXiv results found.")
            return []

        try:
            ranked = self._call_claude(topics, existing, candidates)
        except (anthropic.APIError, json.JSONDecodeError, ValueError) as e:
            print(f"[Recommender] Claude error: {e}")
            return []

        timestamp = datetime.now(timezone.utc).isoformat()
        results = []
        for rec in ranked[:max_results]:
            rec["timestamp"] = timestamp
            self._store_recommendation(rec)
            results.append(rec)

        return results

    def record_feedback(self, arxiv_id: str, rating: str) -> bool:
        """
        Record user feedback on a recommendation.

        rating: "good" | "bad"
        Updates the Recommendation node's feedback property.
        """
        return self.store.update_recommendation_feedback(arxiv_id, rating)

    def get_stored_recommendations(self, limit: int = 5) -> list[dict]:
        """Return the most recent stored recommendations."""
        return self.store.get_recommendations(limit=limit)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _collect_topics(self, papers: list[dict]) -> list[str]:
        seen = []
        for p in papers:
            for t in (p.get("topics") or []):
                if t not in seen:
                    seen.append(t)
        return seen

    def _fmt_existing(self, papers: list[dict]) -> str:
        return "\n".join(
            f"- {p.get('title', 'Untitled')} ({', '.join(p.get('topics') or [])})"
            for p in papers
        )

    def _search_arxiv(self, topics: list[str], per_topic: int = 8) -> list[dict]:
        """Search arXiv for papers matching our topics."""
        client = arxiv.Client()
        seen_ids: set[str] = set()
        results = []

        for topic in topics[:4]:   # cap at 4 topics to avoid too many API calls
            try:
                search = arxiv.Search(
                    query=topic,
                    max_results=per_topic,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                )
                for paper in client.results(search):
                    if paper.entry_id in seen_ids:
                        continue
                    seen_ids.add(paper.entry_id)
                    results.append({
                        "arxiv_id":  paper.entry_id.split("/")[-1],
                        "title":     paper.title,
                        "abstract":  paper.summary[:400],
                        "arxiv_url": paper.entry_id,
                    })
                time.sleep(0.3)   # be polite to arXiv
            except Exception as e:
                print(f"[Recommender] arXiv search error for '{topic}': {e}")

        return results

    def _call_claude(
        self,
        topics: list[str],
        existing: str,
        candidates: list[dict],
    ) -> list[dict]:
        candidates_text = "\n\n".join(
            f"ID: {c['arxiv_id']}\nTitle: {c['title']}\nAbstract: {c['abstract']}"
            for c in candidates
        )
        prompt = RANKING_PROMPT.format(
            topics=", ".join(topics),
            existing=existing,
            candidates=candidates_text,
        )
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        parsed = _parse_json(response.content[0].text)
        if not isinstance(parsed, list):
            raise ValueError("Expected JSON array from Claude")
        return parsed

    def _store_recommendation(self, rec: dict) -> None:
        self.store.upsert_recommendation(rec)
