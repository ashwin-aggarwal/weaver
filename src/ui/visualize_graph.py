"""
Graph Visualization — Obsidian-style

Queries Neo4j for all Paper nodes and CONNECTS_TO edges,
renders an interactive pyvis graph, saves it to weaver_graph.html,
and opens it in the default browser.
"""

import webbrowser
import os
from collections import defaultdict

from pyvis.network import Network

from src.tools.neo4j_store import Neo4jStore

OUTPUT_FILE = "weaver_graph.html"
BG_COLOR    = "#0a0e27"

# ── Topic → color bucket mapping ────────────────────────────────────────────
# Keywords are matched against the topic string (lowercase).
# First match wins. Falls through to the palette if nothing matches.

TOPIC_BUCKETS = [
    ("rag",                          "RAG",       "#00b4d8"),   # cyan-blue
    ("retrieval",                    "RAG",       "#00b4d8"),
    ("neuro",                        "NeuroTech", "#9d4edd"),   # purple
    ("brain",                        "NeuroTech", "#9d4edd"),
    ("motor",                        "NeuroTech", "#9d4edd"),
    ("dynamical",                    "NeuroTech", "#9d4edd"),
    ("neural population",            "NeuroTech", "#9d4edd"),
    ("dimensionality",               "NeuroTech", "#9d4edd"),
    ("bci",                          "NeuroTech", "#9d4edd"),
    ("agentic",                      "AI",        "#f77f00"),   # orange
    ("agent",                        "AI",        "#f77f00"),
    ("large language",               "AI",        "#f77f00"),
    ("llm",                          "AI",        "#f77f00"),
    ("hallucination",                "AI",        "#f77f00"),
    ("machine learning",             "ML",        "#38b000"),   # green
    ("deep learning",                "ML",        "#38b000"),
    ("recurrent",                    "ML",        "#38b000"),
    ("knowledge",                    "Knowledge", "#ffbe0b"),   # amber
    ("information retrieval",        "Knowledge", "#ffbe0b"),
]

FALLBACK_PALETTE = [
    "#e63946", "#a8dadc", "#457b9d", "#f4a261",
    "#2a9d8f", "#e9c46a", "#264653", "#e76f51",
]

# Edge color by connection_type
EDGE_COLORS = {
    "shared_topic":         "#00b4d8",   # cyan
    "shared_method":        "#38b000",   # green
    "bridges_fields":       "#f77f00",   # orange
    "sequential":           "#c77dff",   # lavender
    "contrasting_approach": "#ff6b6b",   # red-pink
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _topic_to_color(topic: str) -> tuple[str, str]:
    """Return (group_name, hex_color) for a topic string."""
    t = topic.lower()
    for keyword, group, color in TOPIC_BUCKETS:
        if keyword in t:
            return group, color
    return topic, ""   # caller handles fallback


def _build_topic_color_map(papers: list[dict]) -> dict[str, str]:
    """
    Map each unique primary topic to a hex color.
    Known bucket topics get their designated color; others get palette colors.
    """
    mapping: dict[str, str] = {}
    fallback_idx = 0
    for p in papers:
        topics  = p.get("topics") or []
        primary = topics[0] if topics else "Unknown"
        if primary in mapping:
            continue
        _, color = _topic_to_color(primary)
        if not color:
            color = FALLBACK_PALETTE[fallback_idx % len(FALLBACK_PALETTE)]
            fallback_idx += 1
        mapping[primary] = color
    return mapping


def _get_all_connections(store: Neo4jStore) -> list[dict]:
    query = """
    MATCH (a:Paper)-[r:CONNECTS_TO]->(b:Paper)
    RETURN a.id AS from_id, b.id AS to_id,
           r.connection_type AS connection_type,
           r.confidence      AS confidence,
           r.reason          AS reason
    """
    try:
        with store._driver.session() as session:
            return [dict(rec) for rec in session.run(query)]
    except Exception as e:
        print(f"[visualize_graph] connection query error: {e}")
        return []


def _short_title(title: str, max_len: int = 38) -> str:
    return title if len(title) <= max_len else title[:max_len - 1] + "…"


def _node_tooltip(p: dict, degree: int) -> str:
    title     = p.get("title", "Untitled")
    topics    = p.get("topics") or []
    year      = p.get("year", "N/A")
    takeaways = (p.get("key_takeaways") or [])[:3]
    ta_html   = "".join(f"<li>{t}</li>" for t in takeaways) if takeaways else "<li>—</li>"
    return (
        f"<div style='max-width:320px;font-family:Inter,sans-serif;'>"
        f"<b style='font-size:14px;'>{title}</b><br>"
        f"<span style='color:#aaa;font-size:11px;'>Year: {year} &nbsp;|&nbsp; "
        f"Connections: {degree}</span><br><br>"
        f"<span style='color:#ccc;font-size:11px;'>Topics: {', '.join(topics[:3])}</span><br><br>"
        f"<b style='font-size:11px;'>Key takeaways:</b>"
        f"<ul style='margin:4px 0 0 16px;font-size:11px;color:#ddd;'>{ta_html}</ul>"
        f"</div>"
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def visualize_graph(output_path: str = OUTPUT_FILE) -> str:
    """Build and open the Obsidian-style interactive graph. Returns HTML path."""
    store = Neo4jStore()
    papers      = store.get_all_papers()
    connections = _get_all_connections(store)
    store.close()

    if not papers:
        print("No papers found in Neo4j. Ingest some papers first.")
        return ""

    # degree (undirected count for sizing)
    degree: dict[str, int] = defaultdict(int)
    for c in connections:
        degree[c["from_id"]] += 1
        degree[c["to_id"]]   += 1

    topic_color = _build_topic_color_map(papers)

    # avg confidence for stats
    confs = [c.get("confidence") or 0.0 for c in connections]
    avg_conf = (sum(confs) / len(confs)) if confs else 0.0

    # ── Network ──────────────────────────────────────────────────────────────
    net = Network(
        height="100vh",
        width="100%",
        bgcolor=BG_COLOR,
        font_color="#ffffff",
        directed=True,
        notebook=False,
    )

    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "solver": "barnesHut",
        "barnesHut": {
          "gravitationalConstant": -30000,
          "centralGravity": 0.15,
          "springLength": 250,
          "springConstant": 0.04,
          "damping": 0.12,
          "avoidOverlap": 0.5
        },
        "stabilization": {
          "enabled": true,
          "iterations": 300,
          "updateInterval": 25,
          "fit": true
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 80,
        "navigationButtons": false,
        "keyboard": { "enabled": true, "speed": { "x": 10, "y": 10, "zoom": 0.02 } },
        "zoomView": true,
        "dragView": true
      },
      "nodes": {
        "shape": "dot",
        "borderWidth": 2,
        "borderWidthSelected": 4,
        "chosen": true,
        "shadow": {
          "enabled": true,
          "color": "rgba(0,0,0,0.6)",
          "size": 12,
          "x": 0,
          "y": 0
        },
        "font": {
          "size": 13,
          "color": "#ffffff",
          "bold": { "mod": "bold" },
          "strokeWidth": 3,
          "strokeColor": "#0a0e27",
          "face": "Inter, Arial, sans-serif"
        }
      },
      "edges": {
        "smooth": { "type": "dynamic" },
        "arrows": { "to": { "enabled": true, "scaleFactor": 0.5 } },
        "font": {
          "size": 9,
          "color": "#8899bb",
          "strokeWidth": 2,
          "strokeColor": "#0a0e27",
          "align": "middle",
          "face": "Inter, Arial, sans-serif"
        },
        "shadow": {
          "enabled": true,
          "color": "rgba(0,0,0,0.4)",
          "size": 5
        },
        "selectionWidth": 3
      }
    }
    """)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    for p in papers:
        pid     = p["id"]
        title   = p.get("title", pid)
        topics  = p.get("topics") or []
        primary = topics[0] if topics else "Unknown"
        color   = topic_color.get(primary, "#888888")

        deg  = degree[pid]
        size = max(18, min(22 + deg * 8, 70))   # 18 base, +8/conn, cap 70

        # glow: highlight color = brighter version of node color, background = transparent
        net.add_node(
            pid,
            label=_short_title(title),
            title=_node_tooltip(p, deg),
            color={
                "background": color,
                "border":     _brighten(color),
                "highlight": {
                    "background": _brighten(color),
                    "border":     "#ffffff",
                },
                "hover": {
                    "background": _brighten(color),
                    "border":     "#ffffff",
                },
            },
            size=size,
        )

    # ── Edges ─────────────────────────────────────────────────────────────────
    for conn in connections:
        ctype      = conn.get("connection_type") or "related"
        confidence = conn.get("confidence")      or 0.0
        reason     = conn.get("reason")          or ""
        edge_color = EDGE_COLORS.get(ctype, "#556688")

        # thickness: 1.5 baseline, bump at high confidence
        width = 1.5 if confidence < 0.8 else 3.5

        tooltip = (
            f"<div style='font-family:Inter,sans-serif;max-width:260px;'>"
            f"<b>{ctype.replace('_', ' ').title()}</b><br>"
            f"<span style='color:#aaa;font-size:11px;'>conf: {confidence:.2f}</span><br><br>"
            f"<span style='font-size:12px;'>{reason}</span>"
            f"</div>"
        )

        net.add_edge(
            conn["from_id"],
            conn["to_id"],
            label=ctype.replace("_", " "),
            title=tooltip,
            color={"color": edge_color, "highlight": "#ffffff", "hover": "#ffffff"},
            width=width,
            dashes=(ctype == "contrasting_approach"),
        )

    # ── Save & inject UI chrome ───────────────────────────────────────────────
    net.save_graph(output_path)

    with open(output_path, "r") as f:
        html = f.read()

    html = html.replace("</head>", _head_inject() + "\n</head>")
    html = html.replace("</body>", _body_inject(
        topic_color, len(papers), len(connections), avg_conf
    ) + "\n</body>")

    with open(output_path, "w") as f:
        f.write(html)

    abs_path = os.path.abspath(output_path)
    print(f"Graph saved → {abs_path}")
    print(f"  {len(papers)} nodes, {len(connections)} edges, avg conf {avg_conf:.2f}")

    webbrowser.open(f"file://{abs_path}")
    return abs_path


# ── Color utilities ───────────────────────────────────────────────────────────

def _brighten(hex_color: str, factor: float = 1.35) -> str:
    """Return a brighter version of a hex color (clamps at 255)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, int(r * factor))
    g = min(255, int(g * factor))
    b = min(255, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


# ── HTML injection ────────────────────────────────────────────────────────────

def _head_inject() -> str:
    return """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #0a0e27; font-family: Inter, Arial, sans-serif; overflow: hidden; }
  #mynetwork { border: none !important; background: #0a0e27 !important; }

  /* search box */
  #search-wrap {
    position: fixed; top: 16px; left: 50%; transform: translateX(-50%);
    z-index: 1000;
  }
  #search-input {
    width: 280px; padding: 8px 14px; border-radius: 20px;
    border: 1px solid #334; background: rgba(10,14,39,0.85);
    color: #fff; font-size: 13px; outline: none;
    backdrop-filter: blur(6px);
  }
  #search-input::placeholder { color: #556; }
  #search-input:focus { border-color: #00b4d8; }

  /* legend */
  #legend {
    position: fixed; top: 16px; left: 16px;
    background: rgba(10,14,39,0.82); border: 1px solid #1e2547;
    border-radius: 10px; padding: 12px 16px; z-index: 999;
    font-size: 12px; color: #ccd; line-height: 2;
    backdrop-filter: blur(6px);
  }
  #legend b { display: block; margin-bottom: 4px; color: #fff; font-size: 13px; }
  .legend-dot {
    display: inline-block; width: 10px; height: 10px;
    border-radius: 50%; margin-right: 6px; vertical-align: middle;
  }

  /* edge legend */
  #edge-legend {
    position: fixed; bottom: 16px; left: 16px;
    background: rgba(10,14,39,0.82); border: 1px solid #1e2547;
    border-radius: 10px; padding: 12px 16px; z-index: 999;
    font-size: 12px; color: #ccd; line-height: 2;
    backdrop-filter: blur(6px);
  }
  #edge-legend b { display: block; margin-bottom: 4px; color: #fff; font-size: 13px; }
  .edge-sample {
    display: inline-block; width: 22px; height: 2px;
    vertical-align: middle; margin-right: 6px; border-radius: 1px;
  }

  /* stats */
  #stats {
    position: fixed; top: 16px; right: 16px;
    background: rgba(10,14,39,0.82); border: 1px solid #1e2547;
    border-radius: 10px; padding: 12px 16px; z-index: 999;
    font-size: 12px; color: #aab; line-height: 1.9;
    backdrop-filter: blur(6px); text-align: right;
  }
  #stats .stat-val { color: #fff; font-weight: 700; font-size: 18px; display: block; }

  /* tooltip override */
  .vis-tooltip {
    background: rgba(10,14,39,0.95) !important;
    border: 1px solid #334 !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    color: #fff !important;
    font-family: Inter, Arial, sans-serif !important;
    font-size: 12px !important;
    max-width: 340px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.6) !important;
  }
</style>"""


def _body_inject(
    topic_color: dict[str, str],
    n_papers: int,
    n_edges: int,
    avg_conf: float,
) -> str:
    # topic legend rows
    legend_rows = "\n".join(
        f'<div><span class="legend-dot" style="background:{c};'
        f'box-shadow:0 0 6px {c};"></span>{t}</div>'
        for t, c in topic_color.items()
    )

    # edge legend rows
    edge_rows = "\n".join(
        f'<div><span class="edge-sample" style="background:{c};"></span>'
        f'{etype.replace("_"," ").title()}</div>'
        for etype, c in [
            ("shared_topic",         "#00b4d8"),
            ("shared_method",        "#38b000"),
            ("bridges_fields",       "#f77f00"),
            ("sequential",           "#c77dff"),
            ("contrasting_approach", "#ff6b6b"),
        ]
    )

    return f"""
<!-- search -->
<div id="search-wrap">
  <input id="search-input" type="text" placeholder="Search papers…" oninput="searchNodes(this.value)">
</div>

<!-- topic legend -->
<div id="legend">
  <b>Topics</b>
  {legend_rows}
</div>

<!-- edge legend -->
<div id="edge-legend">
  <b>Connection types</b>
  {edge_rows}
</div>

<!-- stats -->
<div id="stats">
  <span class="stat-val">{n_papers}</span>papers
  <span class="stat-val">{n_edges}</span>connections
  <span class="stat-val">{avg_conf:.2f}</span>avg confidence
</div>

<script>
// --- search: dim non-matching nodes ---
function searchNodes(query) {{
  if (!network || !network.body) return;
  const q = query.toLowerCase().trim();
  const allNodes = network.body.data.nodes;
  const updates  = [];

  allNodes.forEach(function(node) {{
    const label = (node.label || '').toLowerCase();
    const title = (typeof node.title === 'string' ? node.title : '').toLowerCase();
    const match = !q || label.includes(q) || title.includes(q);
    updates.push({{
      id:      node.id,
      opacity: match ? 1.0 : 0.12,
    }});
  }});
  allNodes.update(updates);
}}

// --- click: highlight neighbours ---
var lastSelected = null;
network.on('click', function(params) {{
  const allNodes = network.body.data.nodes;
  const allEdges = network.body.data.edges;

  if (!params.nodes.length) {{
    // deselect: restore all
    allNodes.update(allNodes.map(n => ({{ id: n.id, opacity: 1.0 }})));
    allEdges.update(allEdges.map(e => ({{ id: e.id, hidden: false }})));
    lastSelected = null;
    return;
  }}

  const selected = params.nodes[0];
  if (lastSelected === selected) {{
    // second click = deselect
    allNodes.update(allNodes.map(n => ({{ id: n.id, opacity: 1.0 }})));
    allEdges.update(allEdges.map(e => ({{ id: e.id, hidden: false }})));
    lastSelected = null;
    return;
  }}
  lastSelected = selected;

  const neighbours = new Set([selected]);
  allEdges.forEach(function(e) {{
    if (e.from === selected || e.to === selected) {{
      neighbours.add(e.from);
      neighbours.add(e.to);
    }}
  }});

  allNodes.update(allNodes.map(n => ({{
    id:      n.id,
    opacity: neighbours.has(n.id) ? 1.0 : 0.08,
  }})));
  allEdges.update(allEdges.map(e => ({{
    id:     e.id,
    hidden: !(neighbours.has(e.from) && neighbours.has(e.to)),
  }})));
}});
</script>"""


if __name__ == "__main__":
    visualize_graph()
