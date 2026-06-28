from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
import config


class Neo4jStore:
    def __init__(self):
        self._driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        )

    def close(self):
        self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # Papers
    # ------------------------------------------------------------------

    def create_paper(self, paper: dict) -> dict | None:
        """
        Create or update a Paper node.

        Required keys: id, title
        Optional keys: abstract, authors, year, url, source
        Returns the stored node as a dict, or None on error.
        """
        query = """
        MERGE (p:Paper {id: $id})
        SET p.title         = $title,
            p.abstract      = $abstract,
            p.authors       = $authors,
            p.year          = $year,
            p.url           = $url,
            p.source        = $source,
            p.topics        = $topics,
            p.key_takeaways = $key_takeaways,
            p.notes         = $notes
        RETURN p
        """
        params = {
            "id":            paper["id"],
            "title":         paper["title"],
            "abstract":      paper.get("abstract", ""),
            "authors":       paper.get("authors", []),
            "year":          paper.get("year"),
            "url":           paper.get("url", ""),
            "source":        paper.get("source", ""),
            "topics":        paper.get("topics", []),
            "key_takeaways": paper.get("key_takeaways", []),
            "notes":         paper.get("notes", ""),
        }
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                return dict(record["p"]) if record else None
        except Neo4jError as e:
            print(f"[Neo4jStore] create_paper error: {e}")
            return None

    def get_paper_by_id(self, paper_id: str) -> dict | None:
        """Return a Paper node by its id, or None if not found."""
        query = "MATCH (p:Paper {id: $id}) RETURN p"
        try:
            with self._driver.session() as session:
                result = session.run(query, id=paper_id)
                record = result.single()
                return dict(record["p"]) if record else None
        except Neo4jError as e:
            print(f"[Neo4jStore] get_paper_by_id error: {e}")
            return None

    def get_all_papers(self) -> list[dict]:
        """Return all Paper nodes as a list of dicts."""
        query = "MATCH (p:Paper) RETURN p"
        try:
            with self._driver.session() as session:
                result = session.run(query)
                return [dict(record["p"]) for record in result]
        except Neo4jError as e:
            print(f"[Neo4jStore] get_all_papers error: {e}")
            return []

    def connection_exists(self, from_id: str, to_id: str) -> bool:
        """Return True if any directed edge already exists between the two papers."""
        query = """
        MATCH (a:Paper {id: $from_id})-[r]->(b:Paper {id: $to_id})
        RETURN count(r) > 0 AS exists
        """
        try:
            with self._driver.session() as session:
                result = session.run(query, from_id=from_id, to_id=to_id)
                record = result.single()
                return bool(record["exists"]) if record else False
        except Neo4jError as e:
            print(f"[Neo4jStore] connection_exists error: {e}")
            return False

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def upsert_recommendation(self, rec: dict) -> bool:
        """Store or update a Recommendation node keyed by arxiv_id."""
        query = """
        MERGE (r:Recommendation {arxiv_id: $arxiv_id})
        SET r.title        = $title,
            r.arxiv_url    = $arxiv_url,
            r.why_relevant = $why_relevant,
            r.confidence   = $confidence,
            r.timestamp    = $timestamp,
            r.feedback     = coalesce(r.feedback, 'none')
        RETURN r
        """
        try:
            with self._driver.session() as session:
                result = session.run(query, {
                    "arxiv_id":     rec.get("arxiv_id", ""),
                    "title":        rec.get("title", ""),
                    "arxiv_url":    rec.get("arxiv_url", ""),
                    "why_relevant": rec.get("why_relevant", ""),
                    "confidence":   rec.get("confidence", 0.0),
                    "timestamp":    rec.get("timestamp", ""),
                })
                return result.single() is not None
        except Neo4jError as e:
            print(f"[Neo4jStore] upsert_recommendation error: {e}")
            return False

    def get_recommendations(self, limit: int = 5) -> list[dict]:
        """Return the most recent recommendations, newest first."""
        query = """
        MATCH (r:Recommendation)
        RETURN r ORDER BY r.timestamp DESC LIMIT $limit
        """
        try:
            with self._driver.session() as session:
                result = session.run(query, limit=limit)
                return [dict(record["r"]) for record in result]
        except Neo4jError as e:
            print(f"[Neo4jStore] get_recommendations error: {e}")
            return []

    def update_recommendation_feedback(self, arxiv_id: str, rating: str) -> bool:
        """Set feedback = 'good' | 'bad' on a Recommendation node."""
        query = """
        MATCH (r:Recommendation {arxiv_id: $arxiv_id})
        SET r.feedback = $rating
        RETURN r
        """
        try:
            with self._driver.session() as session:
                result = session.run(query, arxiv_id=arxiv_id, rating=rating)
                return result.single() is not None
        except Neo4jError as e:
            print(f"[Neo4jStore] update_recommendation_feedback error: {e}")
            return False

    # ------------------------------------------------------------------
    # Connections (edges)
    # ------------------------------------------------------------------

    def create_connection(
        self,
        from_id: str,
        to_id: str,
        rel_type: str = "RELATED_TO",
        properties: dict | None = None,
    ) -> bool:
        """
        Create a directed relationship between two Paper nodes.

        rel_type examples: RELATED_TO, CITES, EXTENDS, CONTRASTS_WITH
        properties: optional dict stored on the edge (e.g. {"reason": "..."})
        Returns True on success, False on error.
        """
        props = properties or {}
        query = f"""
        MATCH (a:Paper {{id: $from_id}})
        MATCH (b:Paper {{id: $to_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        RETURN r
        """
        try:
            with self._driver.session() as session:
                result = session.run(query, from_id=from_id, to_id=to_id, props=props)
                return result.single() is not None
        except Neo4jError as e:
            print(f"[Neo4jStore] create_connection error: {e}")
            return False
