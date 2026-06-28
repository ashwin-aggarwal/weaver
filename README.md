# Weaver: Agentic Research Graph

Auto-discover connections between papers. Get personalized recommendations. Ask questions.

## Quick Start
1. Clone repo
2. Set up Neo4j locally: `docker run -d -p 7687:7687 neo4j`
3. `pip install -r requirements.txt`
4. `streamlit run src/ui/streamlit_app.py`
5. Upload first paper + notes

## How It Works
- **Ingest:** Upload paper PDF + your notes → appears as node
- **Connect:** Agent finds relationships between papers daily
- **Recommend:** Gets 2-3 papers via email at 8am
- **Ask:** Chatbot answers questions about your papers

## Project Structure
See ARCHITECTURE.md for system design.
See SKILL_agents.md for what each agent does.
See SKILL_prompts.md to iterate on agent quality.