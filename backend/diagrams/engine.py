import io
import json
import base64
import re
from typing import Optional

DIAGRAM_RE = re.compile(
    r"---DIAGRAM---\s*\n(.*?)---END DIAGRAM---",
    re.DOTALL,
)

CONCEPTUAL_TYPES = {"flowchart", "concept_map"}


def _mpl_render(fig) -> Optional[bytes]:
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="svg", bbox_inches="tight", dpi=120)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"[Diagram] matplotlib render failed: {e}")
        return None
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def _img_tag(svg_bytes: bytes, alt: str = "Diagram") -> str:
    b64 = base64.b64encode(svg_bytes).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" alt="{alt}">'


_MERMAID_SHAPES = {
    "box": "[{label}]",
    "rectangle": "[{label}]",
    "ellipse": "({label})",
    "oval": "({label})",
    "diamond": "{{{label}}}",
    "rhombus": "{{{label}}}",
    "circle": "(({label}))",
    "parallelogram": "[/{label}\\]",
    "hexagon": "{{{{label}}}}",
    "trapezoid": "[/{label}]",
}


def _mermaid_shape(label: str, shape: str) -> str:
    pattern = _MERMAID_SHAPES.get(shape)
    if pattern:
        return pattern.replace("{label}", label)
    return f"[{label}]"


def _mermaid_id(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "", raw) or "x"


def _mermaid_escape(text: str) -> str:
    return text.replace('"', "'")


def _build_mermaid_graph(
    data: dict,
    default_title: str = "Flowchart",
    edge_label_key: str = "label",
    direction: str = "TD",
) -> Optional[str]:
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not nodes:
        return None

    lines = [f"graph {direction}"]
    title = data.get("title", default_title)
    if title:
        lines.append(f"    %% {title}")

    groups = {}
    for n in nodes:
        nid = _mermaid_id(n.get("id", ""))
        label = n.get("label", nid)
        shape = n.get("shape", "box")
        group = n.get("group", "")
        mnode = _mermaid_shape(label, shape)
        lines.append(f"    {nid}{mnode}")
        if group:
            groups.setdefault(group, []).append(nid)

    for e in edges:
        frm = _mermaid_id(e.get("from", ""))
        to = _mermaid_id(e.get("to", ""))
        elabel = e.get(edge_label_key, "")
        if elabel:
            lines.append(f"    {frm} -->|{_mermaid_escape(elabel)}| {to}")
        else:
            lines.append(f"    {frm} --> {to}")

    if groups:
        # Wrap in subgraphs (rebuild with subgraph layout)
        sg_lines = [f"graph {direction}"]
        if title:
            sg_lines.append(f"    %% {title}")
        seen_in_sg = set()
        for gname, members in groups.items():
            sg_lines.append(f"    subgraph {_mermaid_id(gname)} [{_mermaid_escape(gname)}]")
            for n in nodes:
                nid = _mermaid_id(n.get("id", ""))
                if nid in members:
                    label = n.get("label", nid)
                    shape = n.get("shape", "box")
                    sg_lines.append(f"        {nid}{_mermaid_shape(label, shape)}")
                    seen_in_sg.add(nid)
            sg_lines.append("    end")
        for n in nodes:
            nid = _mermaid_id(n.get("id", ""))
            if nid not in seen_in_sg:
                label = n.get("label", nid)
                shape = n.get("shape", "box")
                sg_lines.append(f"    {nid}{_mermaid_shape(label, shape)}")
        for e in edges:
            frm = _mermaid_id(e.get("from", ""))
            to = _mermaid_id(e.get("to", ""))
            elabel = e.get(edge_label_key, "")
            if elabel:
                sg_lines.append(f"    {frm} -->|{_mermaid_escape(elabel)}| {to}")
            else:
                sg_lines.append(f"    {frm} --> {to}")
        lines = sg_lines

    mermaid_code = "\n".join(lines)
    return f'<div class="mermaid">\n{mermaid_code}\n</div>'


# --- Flowchart ---

def _render_flowchart(data: dict) -> Optional[str]:
    return _build_mermaid_graph(data, "Flowchart", "label", "TD")


# --- Concept Map ---

def _render_concept_map(data: dict) -> Optional[str]:
    return _build_mermaid_graph(data, "Concept Map", "relation", "TD")


# --- Bar Chart ---

def _render_bar(data: dict) -> Optional[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    title = data.get("title", "Bar Chart")
    labels = data.get("labels", [])
    values = data.get("values", [])
    x_label = data.get("x_label", "")
    y_label = data.get("y_label", "")
    if not labels or not values:
        return None
    fig, ax = plt.subplots(figsize=(max(4, len(labels) * 0.5), 3))
    colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(labels)))
    ax.bar(labels, values, color=colors, edgecolor="#333", linewidth=0.5)
    if x_label:
        ax.set_xlabel(x_label, fontsize=9)
    if y_label:
        ax.set_ylabel(y_label, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    svg = _mpl_render(fig)
    return _img_tag(svg, title) if svg else None


# --- Line Chart ---

def _render_line(data: dict) -> Optional[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    title = data.get("title", "Line Chart")
    labels = data.get("labels", [])
    datasets = data.get("datasets", [])
    x_label = data.get("x_label", "")
    y_label = data.get("y_label", "")
    if not labels or not datasets:
        return None
    fig, ax = plt.subplots(figsize=(max(4, len(labels) * 0.4), 3))
    colors = ["#2563EB", "#DC2626", "#16A34A", "#D97706", "#7C3AED", "#0891B2"]
    for i, ds in enumerate(datasets):
        ax.plot(
            labels,
            ds.get("values", []),
            marker="o",
            label=ds.get("name", f"Series {i+1}"),
            color=colors[i % len(colors)],
            linewidth=1.5,
            markersize=4,
        )
    if x_label:
        ax.set_xlabel(x_label, fontsize=9)
    if y_label:
        ax.set_ylabel(y_label, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.legend(fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    svg = _mpl_render(fig)
    return _img_tag(svg, title) if svg else None


# --- Pie Chart ---

def _render_pie(data: dict) -> Optional[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    title = data.get("title", "Pie Chart")
    labels = data.get("labels", [])
    values = data.get("values", [])
    if not labels or not values:
        return None
    fig, ax = plt.subplots(figsize=(4, 3))
    colors = plt.cm.Set2(range(len(labels)))
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        colors=colors,
        textprops={"fontsize": 8},
    )
    ax.set_title(title, fontsize=11, fontweight="bold")
    svg = _mpl_render(fig)
    return _img_tag(svg, title) if svg else None


# --- Venn Diagram ---

def _render_venn(data: dict) -> Optional[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib_venn import venn2, venn3
    title = data.get("title", "Venn Diagram")
    sets = data.get("sets", [])
    intersections = data.get("intersections", [])
    num_sets = len(sets)
    if num_sets < 2 or num_sets > 3:
        return None
    fig, ax = plt.subplots(figsize=(4, 3))
    if num_sets == 2:
        v = venn2(
            subsets=(
                intersections[0]["size"] if len(intersections) > 0 else 0,
                intersections[1]["size"] if len(intersections) > 1 else 0,
                intersections[2]["size"] if len(intersections) > 2 else 0,
            ),
            set_labels=(sets[0]["label"], sets[1]["label"]),
            ax=ax,
        )
    else:
        v = venn3(
            subsets={
                "100": intersections[0]["size"] if len(intersections) > 0 else 0,
                "010": intersections[1]["size"] if len(intersections) > 1 else 0,
                "001": intersections[2]["size"] if len(intersections) > 2 else 0,
                "110": intersections[3]["size"] if len(intersections) > 3 else 0,
                "101": intersections[4]["size"] if len(intersections) > 4 else 0,
                "011": intersections[5]["size"] if len(intersections) > 5 else 0,
                "111": intersections[6]["size"] if len(intersections) > 6 else 0,
            },
            set_labels=(s["label"] for s in sets),
            ax=ax,
        )
    ax.set_title(title, fontsize=11, fontweight="bold")
    svg = _mpl_render(fig)
    return _img_tag(svg, title) if svg else None


# --- Gantt Chart ---

def _render_gantt(data: dict) -> Optional[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    title = data.get("title", "Timeline")
    tasks = data.get("tasks", [])
    if not tasks:
        return None
    names = [t.get("name", f"Task {i+1}") for i, t in enumerate(tasks)]
    starts = [t.get("start", 0) for t in tasks]
    ends = [t.get("end", 1) for t in tasks]
    durations = [e - s for s, e in zip(starts, ends)]
    y_pos = np.arange(len(tasks))
    colors = plt.cm.Paired(np.linspace(0.2, 0.8, len(tasks)))
    fig, ax = plt.subplots(figsize=(max(5, len(tasks) * 0.5), max(2, len(tasks) * 0.4)))
    ax.barh(y_pos, durations, left=starts, color=colors, edgecolor="#333", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel("Time", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    svg = _mpl_render(fig)
    return _img_tag(svg, title) if svg else None


# --- Router ---

RENDERERS = {
    "flowchart": _render_flowchart,
    "concept_map": _render_concept_map,
    "bar": _render_bar,
    "line": _render_line,
    "pie": _render_pie,
    "venn": _render_venn,
    "gantt": _render_gantt,
}


def extract_and_render_diagrams(markdown_text: str) -> str:
    def _replace(match):
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[Diagram] JSON parse error: {e}")
            return f"*[Diagram: invalid JSON]*"
        dtype = data.get("type", "")
        renderer = RENDERERS.get(dtype)
        if not renderer:
            print(f"[Diagram] Unknown type: {dtype}")
            return f"*[Diagram: unknown type '{dtype}']*"
        result = renderer(data)
        if result is None:
            return f"*[Diagram: {dtype} render failed]*"
        return result
    return DIAGRAM_RE.sub(_replace, markdown_text)
