"""
draw.io (diagrams.net) integration for Confluence pages.

Generates draw.io XML diagrams and embeds them in Confluence pages
via the Storage Format macro. Also provides utilities to generate
diagrams from code/data structures.

The draw.io macro in Confluence uses:
  <ac:structured-macro ac:name="drawio">
    <ac:parameter ac:name="diagramName">name</ac:parameter>
    <ac:plain-text-body><![CDATA[...mxfile XML...]]></ac:plain-text-body>
  </ac:structured-macro>

Usage:
    from specialized_agents.jira.drawio import DrawioBuilder, embed_drawio

    # Build a diagram programmatically
    builder = DrawioBuilder("Meu Diagrama")
    n1 = builder.add_node("API Gateway", style="rounded=1;fillColor=#d5e8d4;")
    n2 = builder.add_node("Database", style="shape=cylinder3;fillColor=#e1d5e7;")
    builder.add_edge(n1, n2, label="queries")
    xml = builder.to_xml()

    # Embed in Confluence storage format
    html = embed_drawio("meu-diagrama", xml)
"""
import logging
import re
import uuid
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════ Styles ══════════════════════════════════════════

# Pre-built styles for common diagram elements
STYLES = {
    # Boxes
    "service": "rounded=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=12;fontStyle=1;",
    "app": "rounded=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=14;fontStyle=1;",
    "gateway": "rounded=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=14;fontStyle=1;",
    "warning": "rounded=1;fillColor=#f8cecc;strokeColor=#b85450;fontSize=12;",
    "info": "rounded=1;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=12;",
    "neutral": "rounded=1;fillColor=#f0f0f0;strokeColor=#666666;fontSize=12;",
    # Shapes
    "database": "shape=cylinder3;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=11;",
    "decision": "shape=rhombus;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=11;",
    "start": "shape=ellipse;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=12;",
    "end": "shape=ellipse;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=12;",
    "error": "rounded=1;fillColor=#f8cecc;strokeColor=#b85450;fontSize=10;fontColor=#b85450;",
    # Layers
    "layer_1": "rounded=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=13;fontStyle=1;",
    "layer_2": "rounded=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=13;fontStyle=1;",
    "layer_3": "rounded=1;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=13;fontStyle=1;",
    "layer_4": "rounded=1;fillColor=#f8cecc;strokeColor=#b85450;fontSize=12;",
    "layer_5": "rounded=1;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=12;",
}

# Edge styles
EDGE_STYLES = {
    "default": "edgeStyle=orthogonalEdgeStyle;",
    "curved": "edgeStyle=elbowEdgeStyle;",
    "straight": "",
    "dashed": "edgeStyle=orthogonalEdgeStyle;dashed=1;",
}


# ═══════════════════════════ Builder ═════════════════════════════════════════

class DrawioBuilder:
    """Programmatic builder for draw.io mxfile XML diagrams."""

    def __init__(self, name: str = "Diagram", width: int = 1200, height: int = 800):
        self.name = name
        self.width = width
        self.height = height
        self._nodes: List[Dict] = []
        self._edges: List[Dict] = []
        self._id_counter = 10

    def _next_id(self) -> str:
        self._id_counter += 1
        return str(self._id_counter)

    def add_node(
        self,
        label: str,
        x: int = 0,
        y: int = 0,
        width: int = 160,
        height: int = 50,
        style: str = None,
        style_preset: str = "service",
    ) -> str:
        """Add a node to the diagram. Returns node ID."""
        node_id = self._next_id()
        resolved_style = style or STYLES.get(style_preset, STYLES["service"])
        self._nodes.append({
            "id": node_id,
            "label": label,
            "x": x, "y": y,
            "width": width, "height": height,
            "style": resolved_style,
        })
        return node_id

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        label: str = "",
        style: str = None,
        style_preset: str = "default",
    ) -> str:
        """Add an edge between two nodes. Returns edge ID."""
        edge_id = f"e{self._next_id()}"
        resolved_style = style or EDGE_STYLES.get(style_preset, EDGE_STYLES["default"])
        self._edges.append({
            "id": edge_id,
            "source": source_id,
            "target": target_id,
            "label": label,
            "style": resolved_style,
        })
        return edge_id

    def to_xml(self) -> str:
        """Generate mxfile XML string."""
        cells = []
        for node in self._nodes:
            label = _xml_escape(node["label"])
            cells.append(
                f'        <mxCell id="{node["id"]}" value="{label}" '
                f'style="{node["style"]}" vertex="1" parent="1">'
                f'<mxGeometry x="{node["x"]}" y="{node["y"]}" '
                f'width="{node["width"]}" height="{node["height"]}" as="geometry"/>'
                f'</mxCell>'
            )
        for edge in self._edges:
            label_attr = f' value="{_xml_escape(edge["label"])}"' if edge["label"] else ""
            cells.append(
                f'        <mxCell id="{edge["id"]}"{label_attr} '
                f'style="{edge["style"]}" edge="1" '
                f'source="{edge["source"]}" target="{edge["target"]}" parent="1">'
                f'<mxGeometry relative="1" as="geometry"/>'
                f'</mxCell>'
            )

        nodes_xml = "\n".join(cells)
        return f'''<mxfile>
  <diagram name="{_xml_escape(self.name)}" id="{uuid.uuid4().hex[:8]}">
    <mxGraphModel dx="{self.width}" dy="{self.height}" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="827">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
{nodes_xml}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''


def _xml_escape(text: str) -> str:
    """Escape special XML characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\n", "&#xa;"))


# ═══════════════════════════ Embedding ════════════════════════════════════════

def embed_drawio(diagram_name: str, mxfile_xml: str) -> str:
    """Generate Confluence storage format macro for an embedded draw.io diagram.
    
    Args:
        diagram_name: Unique name for the diagram within the page
        mxfile_xml: Complete mxfile XML string
        
    Returns:
        Confluence storage format HTML with draw.io macro
    """
    return (
        f'<ac:structured-macro ac:name="drawio" ac:schema-version="1" '
        f'ac:macro-id="{diagram_name}">\n'
        f'  <ac:parameter ac:name="diagramName">{diagram_name}</ac:parameter>\n'
        f'  <ac:plain-text-body><![CDATA[{mxfile_xml}]]></ac:plain-text-body>\n'
        f'</ac:structured-macro>'
    )


def embed_drawio_with_fallback(
    diagram_name: str,
    mxfile_xml: str,
    text_fallback: str = "",
) -> str:
    """Embed draw.io diagram with a text/ASCII fallback for non-rendering contexts.
    
    If draw.io for Confluence is not installed, shows the text fallback.
    """
    html = embed_drawio(diagram_name, mxfile_xml)
    if text_fallback:
        html += (
            '\n<ac:structured-macro ac:name="expand" ac:schema-version="1">\n'
            '  <ac:parameter ac:name="title">Versão texto do diagrama</ac:parameter>\n'
            '  <ac:rich-text-body>\n'
            '    <ac:structured-macro ac:name="code" ac:schema-version="1">\n'
            '      <ac:parameter ac:name="language">text</ac:parameter>\n'
            f'      <ac:plain-text-body><![CDATA[{text_fallback}]]></ac:plain-text-body>\n'
            '    </ac:structured-macro>\n'
            '  </ac:rich-text-body>\n'
            '</ac:structured-macro>'
        )
    return html


# ═══════════════════════════ Pre-built Diagrams ══════════════════════════════

def architecture_diagram() -> str:
    """Build the Estou Aqui! architecture diagram."""
    b = DrawioBuilder("Arquitetura Estou Aqui!", 1200, 500)

    # Row 1: Client + Gateway
    app = b.add_node("Mobile App\n(PWA)", x=40, y=40, width=200, height=60, style_preset="app")
    gw = b.add_node("API Gateway\n(FastAPI)", x=340, y=40, width=200, height=60, style_preset="gateway")

    # Row 2: Services
    auth = b.add_node("Auth Service\n(OAuth2 / OIDC)", x=40, y=160, width=180, height=50, style_preset="info")
    events = b.add_node("Event Service", x=240, y=160, width=150, height=50, style_preset="info")
    checkin = b.add_node("Check-in Service\n(Validação)", x=410, y=160, width=170, height=50, style_preset="info")
    risk = b.add_node("Risk Engine", x=600, y=160, width=140, height=50, style_preset="warning")

    # Row 3: Data
    queue = b.add_node("Message Queue\n(NATS/Redis)", x=240, y=280, width=170, height=60, style_preset="database")
    db = b.add_node("PostgreSQL\n+ TimescaleDB", x=40, y=280, width=170, height=60, style_preset="database")
    grafana = b.add_node("Grafana\nDashboards", x=450, y=280, width=140, height=50, style_preset="neutral")
    parquet = b.add_node("Parquet\nExport", x=620, y=280, width=120, height=50, style_preset="neutral")

    # Edges
    b.add_edge(app, gw)
    b.add_edge(gw, auth)
    b.add_edge(gw, events)
    b.add_edge(gw, checkin)
    b.add_edge(checkin, risk)
    b.add_edge(checkin, queue)
    b.add_edge(events, db)
    b.add_edge(queue, db)
    b.add_edge(db, grafana)
    b.add_edge(db, parquet)

    return b.to_xml()


def checkin_flow_diagram() -> str:
    """Build the check-in flow diagram."""
    b = DrawioBuilder("Fluxo de Check-in", 1100, 500)

    start = b.add_node("Participante\nabre app", x=40, y=100, width=140, height=60, style_preset="start")
    scan = b.add_node("Escaneia QR Code\nou entra no raio GPS", x=220, y=100, width=170, height=60, style_preset="info")
    api = b.add_node("API recebe\ncheck-in request", x=430, y=100, width=150, height=60, style_preset="service")
    geo = b.add_node("Validação\nGeotemporal", x=620, y=85, width=140, height=90, style_preset="decision")
    risk = b.add_node("Risk Score\nCalculation", x=800, y=85, width=140, height=90, style_preset="decision")
    queue = b.add_node("Fila de\nMensagens", x=620, y=240, width=120, height=60, style_preset="database")
    persist = b.add_node("Persiste no DB\n(TimescaleDB)", x=800, y=240, width=140, height=60, style_preset="database")
    dash = b.add_node("Dashboard\natualizado", x=800, y=350, width=140, height=50, style_preset="neutral")
    reject = b.add_node("Rejeitado\n(fraude/fora da área)", x=430, y=240, width=150, height=50, style_preset="error")

    b.add_edge(start, scan)
    b.add_edge(scan, api)
    b.add_edge(api, geo)
    b.add_edge(geo, risk, label="OK")
    b.add_edge(geo, reject, label="Fail")
    b.add_edge(risk, queue, label="OK")
    b.add_edge(queue, persist)
    b.add_edge(persist, dash)

    return b.to_xml()


def security_layers_diagram() -> str:
    """Build the security layers diagram."""
    b = DrawioBuilder("Camadas de Segurança", 900, 600)

    layers = [
        ("Camada 1: Autenticação\nOAuth2 + OIDC (Google/Apple)", 40, 700, "layer_1"),
        ("Camada 2: Device Attestation\nPlay Integrity / App Attest", 80, 620, "layer_2"),
        ("Camada 3: Validação Geotemporal\nGPS + janela temporal", 120, 540, "layer_3"),
        ("Camada 4: QR Code Rotativo\nRotação a cada 30s, TOTP", 160, 460, "layer_3"),
        ("Camada 5: Bluetooth Beacon\nProva de proximidade física", 200, 380, "layer_4"),
        ("Camada 6: Motor de Risco\nScore 0-100, classificação", 240, 300, "layer_4"),
        ("Camada 7: Rate Limiting\n1 check-in/usuário/evento", 280, 220, "layer_5"),
    ]

    for i, (label, y_off, width, style) in enumerate(layers):
        b.add_node(label, x=40 + i * 40, y=40 + i * 70, width=width, height=50, style_preset=style)

    return b.to_xml()


# ═══════════════════════════ Sync helpers ═════════════════════════════════════

async def sync_drawio_to_confluence(
    space_key: str = "EA",
    page_title: str = "Arquitetura do Sistema",
    diagram_name: str = "estou-aqui-architecture",
    diagram_xml: str = None,
) -> Dict:
    """Update a Confluence page with a draw.io diagram.
    
    Creates the page if it doesn't exist.
    """
    from .confluence_client import get_confluence_client
    client = get_confluence_client()

    if not client.is_configured:
        return {"error": "Confluence not configured"}

    xml = diagram_xml or architecture_diagram()
    html = embed_drawio_with_fallback(diagram_name, xml)

    # Try to find existing page
    existing = await client.get_page_by_title(space_key, page_title)
    if existing:
        result = await client.update_page(
            existing["id"], page_title, html,
            existing["version"]["number"]
        )
        return {"action": "updated", "page_id": existing["id"], "title": page_title}
    else:
        result = await client.create_page(space_key, page_title, html)
        return {"action": "created", "page_id": result.get("id"), "title": page_title}
