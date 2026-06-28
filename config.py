import os
from dotenv import load_dotenv

load_dotenv()

# --- Anthropic ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-anthropic-api-key")

# --- Neo4j ---
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your-neo4j-password")

# --- Email (Gmail SMTP) ---
EMAIL_ADDRESS  = os.getenv("EMAIL_ADDRESS",  "you@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your-app-password")  # Gmail app password
EMAIL_TO       = os.getenv("EMAIL_TO",       "recipient@example.com")

# --- External APIs ---
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")  # optional
