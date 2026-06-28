from src.agents.ingestion import IngestionAgent
from src.tools.neo4j_store import Neo4jStore
import anthropic

# Setup
neo4j_store = Neo4jStore()
client = anthropic.Anthropic()
agent = IngestionAgent(neo4j_store, client)

# Your data
pdf_path = "/Users/ashwinaggarwal/Downloads/weavertest1.pdf"

user_notes = """
Background Info:
Challenges LLMs face like hallucinations, outdated knowledge, and untraceable reasoning processes.
RAG can help with incorporating knowledge and info from external databases to help with accuracy and
credibility of the generation from the LLM. Particularly helpful for knowledge intensive tasks.

What is covered: Naive RAG, Advanced RAG, Modular RAG

Hallucinations:
- Handling queries beyond their training data or requiring current information
- RAG enhances LLM by retrieving relevant document chunks from external knowledge base through semantic similarity calculation
- Reduces problem of generating factually incorrect content
- Combines the context with the prompts so LLM can give an actual answer

Overview of RAG:

Naive RAG:
- Traditional processes including indexing, retrieval, and generation (Retrieve-Read framework)
- Indexing: Cleaning and extraction of raw data from different file formats (PDF, HTML, MD) → plain text → chunks → vector DB
- Retrieval: Query → vector → compare to indexed chunks → top K most similar
- Generation: Query + retrieved docs synthesized into prompt → LLM response
- Drawbacks: retrieval struggles with precision/recall, hallucination risk, augmentation hurdles (redundancy, relevance), single retrieval may not suffice

Advanced RAG:
- Focuses on enhancing retrieval quality
- Employs pre-retrieval and post-retrieval strategies
- Pre-retrieval: data granularity, index optimization, metadata, alignment, mixed retrieval — making query clearer
- Post-retrieval: re-ranking chunks, context compression, relocating most relevant content to edges of prompt
- Implemented in LlamaIndex, LangChain, HayStack

Modular RAG:
- More adaptability and versatility beyond prior paradigms
- New Modules: Search (direct searches across search engines/KGs), Memory (guides retrieval using LLM memory),
  Routing (selects optimal pathways), Predict (generates context via LLM, reduces noise), Task Adapter (tailors RAG to tasks)
- New Patterns: module substitution/reconfiguration, hybrid retrieval (keyword + semantic + vector)
- Rewrite-Retrieve-Read, Generate-Read, Recite-Read patterns
- Hybrid retrieval: combines keywords, semantics, and vector searches (HyDE)

RAG vs Fine Tuning:
- Prompt Engineering: uses model's inherent capabilities, minimal external knowledge
- RAG: like a tailored textbook — better for precise info retrieval, dynamic environments, real-time updates, sensitive enterprise data. Higher latency drawback.
- Fine Tuning: like a student internalizing a topic — better for style/format replication, deeper customization, reduces hallucinations. Static, needs retraining, computationally expensive.

Retrieval Sources:
- Unstructured (Wikipedia), Semi-Structured (PDFs — risk of splitting tables), Structured (KGs, GNNs, PCST for graph retrieval)

Indexing Optimization:
- Chunking: fixed token splits (256, 512 etc.) — larger = more context but more noise
- Metadata Attachments: page number, filename, author, timestamp → time-aware RAG
- Pre-generating hypothetical questions via LLM and matching user queries to those
- Structural Index: hierarchical parent-child structure, KGs for document structure (nodes = paragraphs/pages/tables, edges = semantic/lexical relationships)

Query Optimization:
- Query Expansion: Multi-Query (parallel LLM-expanded queries), Sub-Queries ("least-to-most" prompting), Chain-of-Verification (CoVe)
- Query Transformation: retrieve based on transformed query (rewrite, step-back prompting)
- Query Routing: route to different RAG pipelines based on query type
- Metadata Filter, Semantic Router

Retrieval:
- Cosine similarity between query and chunk embeddings
- Mix/Hybrid: sparse + dense embeddings capture different relevancies
- Fine-tuning embedding model on domain-specific data improves results

Generation / Context Curation:
- Reranking: reorder chunks by relevance/diversity (BERT-series models)
- Context Compression: remove unimportant tokens (GPT-2 Small as filter, LLM as reranker)
- "Lost in the middle" problem: LLMs focus on start/end of long context, forget middle
- LLM Fine Tuning: targeted fine-tuning for domain gaps; Huggingface data as starting point

Augmentation Strategies:
- Iterative Retrieval: repeatedly search KB based on initial query
- Recursive Retrieval: refine search queries based on previous results (feedback loop)
- Adaptive Retrieval: FLARE and SELF-RAG — LLM actively decides what/when to retrieve (used in AutoGPT)

Evaluation:
- Downstream tasks: QA (single-hop, multi-hop, MCQ, domain-specific, long-form), Information Extraction, dialogue, code search
- Quality Scores: context relevance, answer faithfulness
- Trend: combining RAG + fine-tuning is emerging as leading strategy; SLMs with specific functions (e.g. CRAG)

Key Tools: LangChain, LlamaIndex, Flowise AI (drag-and-drop deployment)
"""

# Run ingestion
result = agent.ingest_paper(pdf_path, user_notes)
print(result)
