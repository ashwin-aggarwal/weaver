"""
Q&A Agent

Answers user questions by retrieving relevant papers from Neo4j and
using Claude to synthesize an answer with cited sources.
"""

import json
import re

import anthropic

SYSTEM_PROMPT = """You are a research assistant with access to a personal knowledge graph
of research papers. Answer questions accurately using only the provided paper excerpts.
Always cite which papers your answer draws from.
Respond ONLY with valid JSON — no explanation, no markdown fences."""

QA_PROMPT = """Answer the following question using the paper excerpts below.

Question: {question}

Papers:
{papers}

Return a JSON object:
{{
  "answer": "<clear, detailed answer drawing from the papers>",
  "sources": [
    {{
      "paper_id":   "<id>",
      "title":      "<paper title>",
      "excerpt":    "<the specific sentence or passage that supports the answer>",
      "confidence": <float 0.0-1.0 — how strongly this paper supports the answer>
    }}
  ]
}}

Rules:
- Only cite papers that directly support the answer
- If no paper addresses the question, set answer to "I don't have enough information in my knowledge graph to answer this." and sources to []
- Keep the answer concise but complete
"""


def _fmt_papers(papers: list[dict]) -> str:
    blocks = []
    for p in papers:
        abstract  = p.get("abstract", "")
        takeaways = p.get("key_takeaways") or []
        notes     = p.get("notes", "")

        content_parts = []
        if abstract:
            content_parts.append(f"Abstract: {abstract}")
        if takeaways:
            content_parts.append("Key takeaways:\n" + "\n".join(f"  - {t}" for t in takeaways))
        if notes:
            content_parts.append(f"Notes: {notes[:500]}")

        blocks.append(
            f"ID: {p['id']}\n"
            f"Title: {p.get('title', 'Untitled')}\n"
            + "\n".join(content_parts)
        )
    return "\n\n---\n\n".join(blocks)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


class QAAgent:
    def __init__(self, neo4j_store, client: anthropic.Anthropic):
        self.store  = neo4j_store
        self.client = client

    def ask(self, question: str) -> dict:
        """
        Answer a question over the knowledge graph.

        Returns:
            {
              "answer":  str,
              "sources": [{"paper_id", "title", "excerpt", "confidence"}]
            }
        """
        papers = self._retrieve_relevant(question)

        if not papers:
            return {
                "answer":  "No papers found in the knowledge graph. Ingest some papers first.",
                "sources": [],
            }

        try:
            result = self._call_claude(question, papers)
        except anthropic.APIError as e:
            return {"answer": f"Claude API error: {e}", "sources": []}
        except (json.JSONDecodeError, KeyError) as e:
            return {"answer": f"Failed to parse Claude response: {e}", "sources": []}

        return result

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def _retrieve_relevant(self, question: str, top_k: int = 3) -> list[dict]:
        """
        Simple keyword retrieval: score each paper by how many question words
        appear in its title + abstract + topics, return top_k.
        """
        all_papers = self.store.get_all_papers()
        if not all_papers:
            return []

        question_words = set(
            w.lower() for w in re.split(r"\W+", question) if len(w) > 3
        )

        def score(p: dict) -> int:
            blob = " ".join([
                p.get("title", ""),
                p.get("abstract", ""),
                " ".join(p.get("topics") or []),
                " ".join(p.get("key_takeaways") or []),
            ]).lower()
            return sum(1 for w in question_words if w in blob)

        ranked = sorted(all_papers, key=score, reverse=True)
        return ranked[:top_k]

    # ------------------------------------------------------------------
    # Claude
    # ------------------------------------------------------------------

    def _call_claude(self, question: str, papers: list[dict]) -> dict:
        prompt = QA_PROMPT.format(
            question=question,
            papers=_fmt_papers(papers),
        )
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json(response.content[0].text)
