# Agent Specifications

## Agent: Ingestion
**Trigger:** User uploads paper + notes
**Task:** Extract metadata, store in Neo4j
**Tools Used:**
  - Neo4j: CREATE (p:Paper) with title, abstract, your_notes
**Output:** {paper_id, success, message}
**Failure Mode:** If PDF parsing fails, ask user to paste abstract

## Agent: Recommender
**Trigger:** Daily at 8am
**Task:** Find 2-3 new papers matching your interests
**Tools Used:**
  - arXiv API search (based on your paper topics)
  - Neo4j query (your past ratings)
  - Claude to rank results by relevance
**Output:** [{paper_title, arxiv_url, why_relevant, confidence}]
**Learning:** User rates (good/bad) → stored in Neo4j → next run uses it

## Agent: Q&A
**Trigger:** User types question
**Task:** Answer using papers + notes, cite sources
**Tools Used:**
  - Neo4j: MATCH papers by relevance to question
  - Claude: Generate answer from context
**Output:** {answer, sources: [{paper, excerpt, confidence}]}