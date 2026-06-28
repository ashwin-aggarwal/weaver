"""
Test: Q&A Agent
Queries the knowledge graph with a real question and verifies the response shape.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from config import ANTHROPIC_API_KEY
from src.tools.neo4j_store import Neo4jStore
from src.agents.qa import QAAgent

def test_qa_agent():
    store  = Neo4jStore()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    agent  = QAAgent(store, client)

    question = "What are the differences between Naive RAG and Advanced RAG?"
    print(f"\nQuestion: {question}\n")

    result = agent.ask(question)

    # ── verify shape ──────────────────────────────────────────────
    assert isinstance(result, dict),           "Result should be a dict"
    assert "answer"  in result,                "Result missing 'answer' key"
    assert "sources" in result,                "Result missing 'sources' key"
    assert isinstance(result["answer"], str),  "Answer should be a string"
    assert len(result["answer"]) > 20,         "Answer is suspiciously short"
    assert isinstance(result["sources"], list),"Sources should be a list"

    print("Answer:")
    print(result["answer"])
    print()

    if result["sources"]:
        print("Sources cited:")
        for src in result["sources"]:
            assert "title"      in src, "Source missing 'title'"
            assert "excerpt"    in src, "Source missing 'excerpt'"
            assert "confidence" in src, "Source missing 'confidence'"
            conf = src["confidence"]
            print(f"  [{conf:.0%}] {src['title']}")
            print(f"        {src['excerpt'][:120]}…")
    else:
        print("(No sources cited)")

    store.close()
    print("\n✓ Q&A Agent test passed")

if __name__ == "__main__":
    test_qa_agent()
