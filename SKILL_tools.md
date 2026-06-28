# Tool Registry

## Neo4j Queries
### Create Paper
MATCH/CREATE (p:Paper) with properties...
Used by: Ingestion Agent

### Find Connected Papers
MATCH (p:Paper)-[:CONNECTS_TO]->(related) WHERE p.id = $id
Used by: Q&A Agent, Recommender Agent

## External APIs
### arXiv Search
GET https://api.semanticscholar.org/graph/v1/paper/search
Parameters: query, limit, fields
Rate limit: 100/min
Used by: Recommender Agent

### Gmail SMTP
smtplib with OAuth2
Used by: Email Agent

## Claude API Calls
### Ingestion Prompt
System: "Extract title, abstract, key takeaways from paper"
Model: claude-opus-4-6
Max tokens: 1000

### Recommender Prompt
System: "You are a research recommender..."
Model: claude-opus-4-6
Max tokens: 2000