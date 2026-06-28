# Weaver Architecture

## Problem
Organize 50-200 research papers, auto-discover connections, get personalized recommendations.

## Solution
Four Claude agents orchestrate around a Neo4j graph.

## Data Model
Papers: {title, abstract, your_notes, topic, upload_date}
Connections: {from_paper, to_paper, type, confidence, reason}

## Agent Orchestration
- Ingestion (on-demand when you upload)
- Connection (daily, batches papers)
- Recommender (daily at 8am, emails results)
- Q&A (on-demand when you ask)

## Why Neo4j?
- Graph queries: "papers connected to X"
- Scales to 200 papers easily
- Real skill to learn

## Decisions Made
- SQLite was rejected because Neo4j teaches graph patterns
- Obsidian rejected because we need agent automation
- Local-only vs cloud: Starting local, can migrate later