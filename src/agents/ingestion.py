"""
Ingestion Agent

Takes a PDF file path + user notes, uses Claude to extract structured metadata,
and stores the result as a Paper node in Neo4j.
"""

import json
import pathlib
import base64
import hashlib
import re

import anthropic
from config import ANTHROPIC_API_KEY
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a research paper analysis assistant.
Given a research paper (as a PDF) and optional user notes, extract structured metadata.
Respond ONLY with valid JSON — no explanation, no markdown fences."""

EXTRACTION_PROMPT = """Extract the following from the paper and user notes below.

Return a JSON object with exactly these keys:
{{
  "title":         "<full paper title>",
  "abstract":      "<paper abstract, or a 2-3 sentence summary if absent>",
  "authors":       ["<author 1>", "<author 2>"],
  "year":          <4-digit year as integer, or null>,
  "topics":        ["<topic 1>", "<topic 2>", ...],
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", ...]
}}

Rules:
- topics: 3-7 high-level themes inferred from title, abstract, and notes
- key_takeaways: bullet-point insights drawn primarily from the user notes (fall back to paper content if notes are sparse)
- If a field cannot be determined, use null (scalars) or [] (arrays)

User notes:
{notes}
"""


class IngestionAgent:
    def __init__(self, neo4j_store, client: anthropic.Anthropic):
        self.store = neo4j_store
        self.client = client

    def ingest_paper(self, pdf_path: str, notes: str = "") -> dict:
        """
        Parse a PDF + user notes with Claude and store the result in Neo4j.

        Returns: {"paper_id": str, "success": bool, "message": str}
        """
        # --- validate file ---
        path = pathlib.Path(pdf_path)
        if not path.exists():
            return {"paper_id": None, "success": False, "message": f"File not found: {pdf_path}"}
        if path.suffix.lower() != ".pdf":
            return {"paper_id": None, "success": False, "message": f"Expected a PDF, got: {path.suffix}"}

        # --- extract metadata via Claude ---
        try:
            metadata = self._call_claude(path, notes)
        except json.JSONDecodeError as e:
            return {"paper_id": None, "success": False, "message": f"Claude returned invalid JSON: {e}"}
        except anthropic.APIError as e:
            return {"paper_id": None, "success": False, "message": f"Claude API error: {e}"}
        except Exception as e:
            return {"paper_id": None, "success": False, "message": f"Extraction failed: {e}"}

        if not metadata.get("title"):
            return {"paper_id": None, "success": False, "message": "Could not extract title from paper."}

        # --- build paper dict ---
        paper_id = self._paper_id(path)
        paper = {
            "id":            paper_id,
            "title":         metadata["title"],
            "abstract":      metadata.get("abstract", ""),
            "authors":       metadata.get("authors", []),
            "year":          metadata.get("year"),
            "topics":        metadata.get("topics", []),
            "key_takeaways": metadata.get("key_takeaways", []),
            "source":        "pdf",
            "url":           "",
            "notes":         notes,
        }

        # --- store in Neo4j ---
        try:
            result = self.store.create_paper(paper)
        except Exception as e:
            return {"paper_id": None, "success": False, "message": f"Neo4j error: {e}"}

        if result is None:
            return {"paper_id": paper_id, "success": False, "message": "Neo4j write returned no result."}

        return {
            "paper_id": paper_id,
            "success":  True,
            "message":  f"Ingested '{metadata['title']}' (id={paper_id})",
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _call_claude(self, path: pathlib.Path, notes: str) -> dict:
        pdf_b64 = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        prompt = EXTRACTION_PROMPT.format(notes=notes or "(none)")

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)

    @staticmethod
    def _paper_id(path: pathlib.Path) -> str:
        """Stable ID: first 16 hex chars of the file's SHA-256."""
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
