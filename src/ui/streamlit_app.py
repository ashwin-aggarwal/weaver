"""
Weaver — Streamlit Frontend
"""

import sys
import os

# Ensure project root is on the path regardless of where streamlit is launched from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import os
import tempfile

import streamlit as st
import anthropic

from src.tools.neo4j_store import Neo4jStore
from src.agents.ingestion import IngestionAgent
from src.agents.connection_generator import ConnectionGeneratorAgent
from src.agents.qa import QAAgent
from src.agents.recommender import RecommenderAgent
from src.tools.email_sender import send_recommendations
from src.ui.visualize_graph import visualize_graph
from config import ANTHROPIC_API_KEY

# ------------------------------------------------------------------
# Shared resources (cached so they aren't re-created on every rerun)
# ------------------------------------------------------------------

@st.cache_resource
def get_store():
    return Neo4jStore()

@st.cache_resource
def get_client():
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(
    page_title="Weaver",
    page_icon="🕸️",
    layout="wide",
)

st.sidebar.title("🕸️ Weaver")
st.sidebar.caption("Your personal research knowledge graph")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Agents**\n"
    "- 📄 Ingest papers\n"
    "- 🔗 Generate connections\n"
    "- ❓ Ask questions\n"
    "- 🔍 Get recommendations\n"
)

store  = get_store()
client = get_client()

# ------------------------------------------------------------------
# Tabs
# ------------------------------------------------------------------

tab_ingest, tab_graph, tab_qa, tab_recs = st.tabs([
    "📄 Upload & Ingest",
    "🔗 Knowledge Graph",
    "❓ Ask Questions",
    "🔍 Paper Recommendations",
])

# ── Tab 1: Upload & Ingest ─────────────────────────────────────────

with tab_ingest:
    st.header("Upload & Ingest a Paper")
    st.caption("Upload a PDF and add your notes. Weaver will extract metadata and add it to your knowledge graph.")

    uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"])
    user_notes    = st.text_area("Your notes (optional)", height=200,
                                 placeholder="Key ideas, takeaways, questions…")

    if st.button("Ingest Paper", type="primary", disabled=uploaded_file is None):
        with st.spinner("Extracting metadata with Claude…"):
            # write upload to a temp file
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            agent  = IngestionAgent(store, client)
            result = agent.ingest_paper(tmp_path, user_notes)
            os.unlink(tmp_path)

        if result["success"]:
            st.success(f"✓ {result['message']}")
            st.json(result)
        else:
            st.error(f"✗ {result['message']}")

    st.markdown("---")
    st.subheader("Papers in Graph")
    papers = store.get_all_papers()
    if papers:
        for p in papers:
            with st.expander(p.get("title", p["id"])):
                st.write(f"**Year:** {p.get('year', 'N/A')}")
                st.write(f"**Authors:** {', '.join(p.get('authors') or [])}")
                st.write(f"**Topics:** {', '.join(p.get('topics') or [])}")
                st.write(f"**Abstract:** {p.get('abstract', '')[:300]}…")
    else:
        st.info("No papers ingested yet.")

# ── Tab 2: Knowledge Graph ─────────────────────────────────────────

with tab_graph:
    st.header("Knowledge Graph")

    col1, col2 = st.columns([1, 3])

    with col1:
        papers = store.get_all_papers()
        st.metric("Papers", len(papers))

        if st.button("🔗 Regenerate Connections", type="primary"):
            with st.spinner("Finding connections with Claude…"):
                agent  = ConnectionGeneratorAgent(store, client)
                result = agent.generate_connections()
            st.success(
                f"✓ {result['connections_created']} connections created, "
                f"{result['connections_skipped']} skipped"
            )

        if st.button("🔄 Refresh Graph"):
            with st.spinner("Rendering graph…"):
                html_path = visualize_graph()
            st.success(f"Graph saved to {html_path}")

    with col2:
        graph_path = "weaver_graph.html"
        if os.path.exists(graph_path):
            with open(graph_path, "r") as f:
                html_content = f.read()
            st.components.v1.html(html_content, height=600, scrolling=False)
        else:
            st.info("No graph yet. Click 'Regenerate Connections' to build one.")

# ── Tab 3: Ask Questions ───────────────────────────────────────────

with tab_qa:
    st.header("Ask Questions")
    st.caption("Ask anything about the papers in your knowledge graph.")

    question = st.text_input("Your question", placeholder="What are the main differences between Naive RAG and Advanced RAG?")

    if st.button("Ask", type="primary", disabled=not question):
        with st.spinner("Searching knowledge graph and generating answer…"):
            agent  = QAAgent(store, client)
            result = agent.ask(question)

        st.markdown("### Answer")
        st.write(result["answer"])

        if result.get("sources"):
            st.markdown("### Sources")
            for src in result["sources"]:
                conf = src.get("confidence", 0)
                with st.expander(f"📄 {src.get('title', 'Unknown')}  —  confidence {conf:.0%}"):
                    st.write(src.get("excerpt", ""))

# ── Tab 4: Paper Recommendations ──────────────────────────────────

with tab_recs:
    st.header("Paper Recommendations")
    st.caption("Discover new papers relevant to your research topics.")

    if st.button("🔍 Get New Recommendations", type="primary"):
        with st.spinner("Searching arXiv and ranking with Claude…"):
            agent = RecommenderAgent(store, client)
            recs  = agent.get_recommendations(max_results=3)

        if recs:
            st.success(f"Found {len(recs)} recommendations")
        else:
            st.warning("No recommendations found. Try ingesting more papers first.")

    st.markdown("---")
    st.subheader("Recent Recommendations")

    stored_recs = store.get_recommendations(limit=5)

    if not stored_recs:
        st.info("No recommendations yet. Click 'Get New Recommendations'.")
    else:
        for rec in stored_recs:
            with st.container():
                col_title, col_feedback = st.columns([4, 1])
                with col_title:
                    title = rec.get("title", "Untitled")
                    url   = rec.get("arxiv_url", "#")
                    st.markdown(f"**[{title}]({url})**")
                    st.caption(rec.get("why_relevant", ""))
                    conf = rec.get("confidence", 0)
                    st.progress(conf, text=f"Relevance: {conf:.0%}")

                with col_feedback:
                    feedback = rec.get("feedback", "none")
                    arxiv_id = rec.get("arxiv_id", "")

                    if feedback == "good":
                        st.markdown("👍 Liked")
                    elif feedback == "bad":
                        st.markdown("👎 Disliked")
                    else:
                        if st.button("👍", key=f"good_{arxiv_id}"):
                            store.update_recommendation_feedback(arxiv_id, "good")
                            st.rerun()
                        if st.button("👎", key=f"bad_{arxiv_id}"):
                            store.update_recommendation_feedback(arxiv_id, "bad")
                            st.rerun()

                st.markdown("---")

    # Email section
    if stored_recs:
        st.subheader("Email Recommendations")
        if st.button("📧 Send Recommendations by Email"):
            with st.spinner("Sending email…"):
                result = send_recommendations(stored_recs)
            if result["success"]:
                st.success(f"✓ {result['message']}")
            else:
                st.error(f"✗ {result['message']}")
