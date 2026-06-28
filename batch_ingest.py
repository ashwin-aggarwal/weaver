import os
import anthropic
from config import ANTHROPIC_API_KEY
from src.agents.ingestion import IngestionAgent
from src.tools.neo4j_store import Neo4jStore

PAPERS_DIR = "data/papers"

neo4j_store = Neo4jStore()
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
agent = IngestionAgent(neo4j_store, client)

pdf_files = [f for f in os.listdir(PAPERS_DIR) if f.lower().endswith(".pdf")]

if not pdf_files:
    print(f"No PDF files found in {PAPERS_DIR}/")
    neo4j_store.close()
    exit(0)

successful = 0
failed = 0

for filename in pdf_files:
    pdf_path = os.path.join(PAPERS_DIR, filename)
    user_notes = f"Paper: {filename}"

    print(f"Ingesting {filename}...")

    result = agent.ingest_paper(pdf_path, user_notes)

    if result["success"]:
        successful += 1
        print(f"✓ {result['message']}")
    else:
        failed += 1
        print(f"✗ Failed to ingest {filename}: {result['message']}")

neo4j_store.close()
print(f"\nSummary: {successful} successful, {failed} failed")
