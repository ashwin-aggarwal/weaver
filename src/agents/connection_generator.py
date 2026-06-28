"""
Connection Generator Agent

Finds intellectual relationships between papers already stored in Neo4j
and writes them as edges: (Paper)-[:CONNECTS_TO]->(Paper).

Strategy
--------
1. Load all papers from Neo4j.
2. Group papers by shared topics  →  within-topic comparison batches.
3. Build cross-topic batches by pairing topic groups that have ≥1 paper in common.
4. For each batch: send 3-5 source papers vs 10-15 candidates to Claude.
5. Store only connections with confidence >= 0.8.
"""

import json
import re
from collections import defaultdict
from itertools import combinations

import anthropic

CONFIDENCE_THRESHOLD = 0.8

SYSTEM_PROMPT = """You are a research graph analyst.
Given a set of source papers and candidate papers, identify strong intellectual
connections between them. Be selective — only surface connections with genuine,
deep overlap. 2-3 strong connections per source paper is better than 10 weak ones.
Respond ONLY with valid JSON — no explanation, no markdown fences."""

CONNECTION_PROMPT = """Analyze the source papers below and find strong connections to
the candidate papers.

Connection types:
- shared_method     : both papers use the same core technique or methodology
- shared_topic      : both papers address the same high-level research problem
- bridges_fields    : one paper applies ideas from another field to close a gap
- sequential        : one paper directly builds on or extends the other's work
- contrasting_approach : papers tackle the same problem with opposing strategies

Confidence guide (be strict):
  >= 0.8  → strong, store it
  0.7-0.8 → uncertain, do NOT include
  < 0.7   → skip

Return a JSON array (empty array if no strong connections found):
[
  {{
    "from_id":         "<source paper id>",
    "to_id":           "<candidate paper id>",
    "connection_type": "<one of the types above>",
    "reason":          "<one concise sentence explaining the connection>",
    "confidence":      <float 0.0-1.0>
  }},
  ...
]

--- SOURCE PAPERS ---
{sources}

--- CANDIDATE PAPERS ---
{candidates}
"""


def _fmt_papers(papers: list[dict]) -> str:
    """Render a list of paper dicts as a numbered block for the prompt."""
    lines = []
    for p in papers:
        lines.append(
            f"ID: {p['id']}\n"
            f"Title: {p['title']}\n"
            f"Abstract: {p.get('abstract', '(none)')}\n"
            f"Topics: {', '.join(p.get('topics') or [])}\n"
        )
    return "\n".join(lines)


def _parse_json(raw: str) -> list:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


class ConnectionGeneratorAgent:
    def __init__(self, neo4j_store, client: anthropic.Anthropic):
        self.store = neo4j_store
        self.client = client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_connections(self) -> dict:
        """
        Find and store all strong connections between papers in the graph.

        Returns:
            {
              "connections_created": int,
              "connections_skipped": int,   # low confidence or already existed
              "batches_processed":  int,
              "errors":             int,
            }
        """
        papers = self.store.get_all_papers()
        valid = [p for p in papers if p.get("abstract") and p.get("title")]

        if len(valid) < 2:
            print("Not enough papers with abstracts to generate connections.")
            return {"connections_created": 0, "connections_skipped": 0,
                    "batches_processed": 0, "errors": 0}

        print(f"Loaded {len(valid)} papers from Neo4j.")

        batches = self._build_batches(valid)
        print(f"Built {len(batches)} comparison batches.")

        created = skipped = errors = 0

        for i, (sources, candidates) in enumerate(batches, 1):
            print(f"  Batch {i}/{len(batches)}: "
                  f"{len(sources)} sources × {len(candidates)} candidates …")
            try:
                connections = self._call_claude(sources, candidates)
            except anthropic.APIError as e:
                print(f"    ✗ Claude API error: {e}")
                errors += 1
                continue
            except (json.JSONDecodeError, ValueError) as e:
                print(f"    ✗ JSON parse error: {e}")
                errors += 1
                continue

            for conn in connections:
                if conn.get("confidence", 0) < CONFIDENCE_THRESHOLD:
                    skipped += 1
                    continue
                if conn["from_id"] == conn["to_id"]:
                    skipped += 1
                    continue
                if self.store.connection_exists(conn["from_id"], conn["to_id"]):
                    skipped += 1
                    continue

                stored = self.store.create_connection(
                    from_id=conn["from_id"],
                    to_id=conn["to_id"],
                    rel_type="CONNECTS_TO",
                    properties={
                        "connection_type": conn.get("connection_type", ""),
                        "reason":          conn.get("reason", ""),
                        "confidence":      conn.get("confidence", 0.0),
                    },
                )
                if stored:
                    created += 1
                    print(f"    ✓ {conn['from_id'][:8]} → {conn['to_id'][:8]} "
                          f"[{conn.get('connection_type')}] conf={conn.get('confidence'):.2f}")
                else:
                    errors += 1

        print(f"\nDone. {created} connections created, "
              f"{skipped} skipped, {errors} errors.")
        return {
            "connections_created": created,
            "connections_skipped": skipped,
            "batches_processed":   len(batches),
            "errors":              errors,
        }

    # ------------------------------------------------------------------
    # Batch building
    # ------------------------------------------------------------------

    def _build_batches(
        self, papers: list[dict]
    ) -> list[tuple[list[dict], list[dict]]]:
        """
        Return a list of (sources, candidates) tuples.

        Within-topic: for each topic that has ≥2 papers, compare all of them
        against each other in windows of up to 5 sources × 15 candidates.

        Cross-topic: for every pair of topic groups, pick up to 3 papers from
        each side and compare them against each other.
        """
        id_map = {p["id"]: p for p in papers}

        # group paper IDs by topic
        topic_groups: dict[str, list[str]] = defaultdict(list)
        for p in papers:
            for topic in (p.get("topics") or []):
                topic_groups[topic].append(p["id"])

        batches: list[tuple[list[dict], list[dict]]] = []
        seen_pairs: set[frozenset] = set()

        def _add_batch(src_ids: list[str], cand_ids: list[str]) -> None:
            pair_key = frozenset([frozenset(src_ids), frozenset(cand_ids)])
            if pair_key in seen_pairs:
                return
            seen_pairs.add(pair_key)
            src   = [id_map[i] for i in src_ids  if i in id_map]
            cands = [id_map[i] for i in cand_ids if i in id_map]
            if src and cands:
                batches.append((src, cands))

        # within-topic batches
        for topic, ids in topic_groups.items():
            if len(ids) < 2:
                continue
            unique = list(dict.fromkeys(ids))   # preserve order, dedupe
            # slide a window: first 5 as sources, remaining (up to 15) as candidates
            for start in range(0, len(unique), 5):
                sources    = unique[start : start + 5]
                candidates = [i for i in unique if i not in sources][:15]
                if candidates:
                    _add_batch(sources, candidates)

        # cross-topic batches (every pair of distinct topic groups)
        topic_list = list(topic_groups.items())
        for (t1, ids1), (t2, ids2) in combinations(topic_list, 2):
            unique1 = list(dict.fromkeys(ids1))[:3]
            unique2 = list(dict.fromkeys(ids2))[:3]
            if unique1 and unique2:
                _add_batch(unique1, unique2)
                _add_batch(unique2, unique1)

        return batches

    # ------------------------------------------------------------------
    # Claude call
    # ------------------------------------------------------------------

    def _call_claude(
        self, sources: list[dict], candidates: list[dict]
    ) -> list[dict]:
        prompt = CONNECTION_PROMPT.format(
            sources=_fmt_papers(sources),
            candidates=_fmt_papers(candidates),
        )
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        parsed = _parse_json(raw)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON array, got: {type(parsed)}")
        return parsed
