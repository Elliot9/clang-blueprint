"""
mermaid_generator.py — Generate Mermaid class, sequence, and FSM diagrams
from blueprint_index entries and call graph data.

Supports filtering by namespace or class-name regex pattern.
"""

from __future__ import annotations

import re
import textwrap
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_id(name: str) -> str:
    """
    Convert a potentially qualified C++ name to a safe Mermaid node ID.
    Replaces '::', '<', '>', ',', ' ' with underscore.
    """
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def _matches_filter(
    entry: dict[str, Any],
    filter_pattern: Optional[str],
    namespace_filter: Optional[str],
) -> bool:
    """Return True if an entry passes the optional filter criteria."""
    if namespace_filter:
        ns = entry.get("namespace", "")
        if not ns.startswith(namespace_filter):
            return False
    if filter_pattern:
        pattern = re.compile(filter_pattern, re.IGNORECASE)
        if not pattern.search(entry.get("className", "")):
            return False
    return True


def _format_method_label(sig: str) -> str:
    """
    Shorten a method signature for display in Mermaid.
    Keep only name + abbreviated params.
    """
    # Strip return type: method name is the last whitespace-delimited token
    # before '('. Supports destructors (~Name) and multi-token return types.
    sig = sig.strip()
    if "(" not in sig or not sig.endswith(")"):
        return sig[:60]
    i = sig.rfind("(")
    param_blob = sig[i + 1 : -1]
    prefix = sig[:i].rstrip()
    tokens = prefix.split()
    if not tokens:
        return sig[:60]
    name = tokens[-1]
    params = param_blob
    # Abbreviate long param lists
    param_parts = [p.strip() for p in params.split(",") if p.strip()]
    if len(param_parts) > 2:
        params_str = ", ".join(param_parts[:2]) + ", ..."
    else:
        params_str = ", ".join(param_parts)
    return f"{name}({params_str})"


# ---------------------------------------------------------------------------
# Class diagram
# ---------------------------------------------------------------------------

def generate_class_diagram(
    entries: list[dict[str, Any]],
    filter_pattern: Optional[str] = None,
    namespace_filter: Optional[str] = None,
    max_methods: int = 6,
    max_attributes: int = 12,
    title: Optional[str] = None,
) -> str:
    """
    Generate a Mermaid classDiagram from blueprint_index entries.

    Args:
        entries: List of blueprint_index entry dicts.
        filter_pattern: Optional regex pattern to match against className.
        namespace_filter: Optional namespace prefix to restrict output.
        max_methods: Maximum number of methods to show per class (keeps diagram readable).
        max_attributes: Maximum number of fields to show per class.
        title: Optional diagram title.

    Returns:
        Mermaid diagram string.
    """
    filtered = [
        e for e in entries
        if _matches_filter(e, filter_pattern, namespace_filter)
    ]

    if not filtered:
        return "classDiagram\n    note \"No matching classes found\""

    # Build set of class names present in filtered set
    present_classes: set[str] = {e["className"] for e in filtered}

    lines: list[str] = ["classDiagram"]
    if title:
        lines.append(f'    title {title}')

    # Collect all relationships to emit after class definitions
    relationships: list[str] = []

    dep_arrow_map = {
        "inheritance": "<|--",
        "composition": "*--",
        "association": "-->",
        "dependency": "..>",
    }

    for entry in filtered:
        class_name = entry["className"]
        safe_id = _sanitize_id(class_name)

        # Class block
        lines.append(f"    class {safe_id} {{")

        # Template params as note
        tp = entry.get("templateParams", [])
        if tp:
            lines.append(f"        <<template>>")

        # Member fields (visibility + type + name, from FIELD_DECL)
        attrs = entry.get("attributes") or []
        shown_attrs = attrs[:max_attributes]
        for raw in shown_attrs:
            label = raw.replace("<", "~").replace(">", "~")
            lines.append(f"        {label}")
        if len(attrs) > max_attributes:
            lines.append(f"        ... {len(attrs) - max_attributes} more fields")

        # Interfaces / methods
        ifaces = entry.get("interfaces", [])
        shown = ifaces[:max_methods]
        for iface in shown:
            label = _format_method_label(iface)
            # Escape special chars for Mermaid
            label = label.replace("<", "~").replace(">", "~")
            lines.append(f"        +{label}")
        if len(ifaces) > max_methods:
            lines.append(f"        ... {len(ifaces) - max_methods} more")

        lines.append("    }")

        # Namespace note
        ns = entry.get("namespace", "")
        if ns:
            lines.append(f'    note for {safe_id} "ns: {ns}"')

        # Relationships — only draw if the target is in our filtered set
        for dep in entry.get("dependencies", []):
            target = dep["target"]
            dep_type = dep["type"]
            # Strip template arguments for lookup
            target_base = re.sub(r"<.*>", "", target).strip().split("::")[-1]

            if target_base not in present_classes and target not in present_classes:
                continue  # Don't draw edges to classes outside diagram

            safe_target = _sanitize_id(target_base)
            arrow = dep_arrow_map.get(dep_type, "-->")

            if dep_type == "inheritance":
                # Mermaid: ParentClass <|-- ChildClass
                rel = f"    {safe_target} {arrow} {safe_id}"
            else:
                label = dep_type
                card = dep.get("cardinality")
                if card:
                    label = f"{dep_type} [{card}]"
                rel = f"    {safe_id} {arrow} {safe_target} : {label}"

            if rel not in relationships:
                relationships.append(rel)

    lines.extend(relationships)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sequence diagram
# ---------------------------------------------------------------------------

def generate_sequence_diagram(
    call_graph: list[dict[str, Any]],
    filter_pattern: Optional[str] = None,
    namespace_filter: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """
    Generate a Mermaid sequenceDiagram from call graph data.

    The call graph format is:
    [
      {
        "caller": "ClassName::methodName",
        "callee": "ClassName::methodName",
        "args": "optional arg description",
        "return": "optional return description"
      },
      ...
    ]

    This matches the output format used for GDB backtrace comparison.

    Args:
        call_graph: List of call edges.
        filter_pattern: Regex to filter caller/callee by class name.
        namespace_filter: Namespace prefix filter (applied to class name part).
        title: Optional diagram title.

    Returns:
        Mermaid sequence diagram string.
    """
    if not call_graph:
        return "sequenceDiagram\n    Note over System: No call graph data"

    def _class_of(qualified: str) -> str:
        parts = qualified.rsplit("::", 1)
        return parts[0] if len(parts) == 2 else qualified

    def _method_of(qualified: str) -> str:
        parts = qualified.rsplit("::", 1)
        return parts[-1]

    # Apply filters
    filtered_edges = []
    for edge in call_graph:
        caller = edge.get("caller", "")
        callee = edge.get("callee", "")
        caller_cls = _class_of(caller)
        callee_cls = _class_of(callee)

        if namespace_filter:
            if not (caller_cls.startswith(namespace_filter) or
                    callee_cls.startswith(namespace_filter)):
                continue
        if filter_pattern:
            pat = re.compile(filter_pattern, re.IGNORECASE)
            if not (pat.search(caller_cls) or pat.search(callee_cls)):
                continue
        filtered_edges.append(edge)

    if not filtered_edges:
        return "sequenceDiagram\n    Note over System: No matching call graph edges"

    # Collect unique participants in order of first appearance
    participants: list[str] = []
    seen_participants: set[str] = set()
    for edge in filtered_edges:
        for role in ("caller", "callee"):
            cls = _sanitize_id(_class_of(edge.get(role, "")))
            if cls not in seen_participants:
                seen_participants.add(cls)
                participants.append(cls)

    lines: list[str] = ["sequenceDiagram"]
    if title:
        lines.append(f"    title {title}")

    for p in participants:
        lines.append(f"    participant {p}")

    lines.append("")

    for edge in filtered_edges:
        caller_cls = _sanitize_id(_class_of(edge.get("caller", "")))
        callee_cls = _sanitize_id(_class_of(edge.get("callee", "")))
        method = _method_of(edge.get("callee", "unknown"))
        args = edge.get("args", "")
        ret = edge.get("return", "")

        call_label = f"{method}({args})" if args else f"{method}()"
        # Truncate long labels
        if len(call_label) > 60:
            call_label = call_label[:57] + "..."

        lines.append(f"    {caller_cls}->>+{callee_cls}: {call_label}")
        if ret:
            ret_label = str(ret)[:60]
            lines.append(f"    {callee_cls}-->>-{caller_cls}: {ret_label}")
        else:
            lines.append(f"    {callee_cls}-->>-{caller_cls}: return")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GDB backtrace → call graph converter
# ---------------------------------------------------------------------------

def parse_gdb_backtrace(backtrace_text: str) -> list[dict[str, Any]]:
    """
    Convert a GDB backtrace string into call graph edges.

    Handles formats like:
        #0  DiskManager::readBlock (this=0x..., lba=0, buf=0x...) at disk_mgr.cpp:55
        #1  FileSystem::open (this=0x..., path="/etc/fstab") at fs.cpp:123
        ...

    Returns list of call graph edge dicts (callee at lower frame #, caller at higher #).
    """
    frame_re = re.compile(
        r"#(\d+)\s+"
        r"(?:0x[0-9a-fA-F]+\s+in\s+)?"
        r"([\w:<>~,\s*&]+?)"   # function name (may contain template params)
        r"\s*\("
        r"([^)]*)"             # arguments
        r"\)"
        r"(?:\s+at\s+([\w./]+):(\d+))?",
        re.MULTILINE,
    )

    frames: list[dict[str, Any]] = []
    for m in frame_re.finditer(backtrace_text):
        frame_num = int(m.group(1))
        func_name = m.group(2).strip()
        args_raw = m.group(3).strip()
        file_loc = m.group(4) or ""
        line_num = int(m.group(5)) if m.group(5) else 0

        # Parse class::method
        parts = func_name.rsplit("::", 1)
        class_name = parts[0] if len(parts) == 2 else "global"
        method_name = parts[-1]

        # Parse args — filter out "this=..." pointer
        args_display = ", ".join(
            a.strip()
            for a in args_raw.split(",")
            if not a.strip().startswith("this=")
        )

        frames.append({
            "frame": frame_num,
            "qualified": func_name,
            "class": class_name,
            "method": method_name,
            "args": args_display,
            "file": file_loc,
            "line": line_num,
        })

    # Frames are bottom-up in GDB (#0 = innermost). Build call edges:
    # frame N calls frame N-1, so frame[i+1].caller → frame[i].callee
    frames.sort(key=lambda f: f["frame"])
    edges: list[dict[str, Any]] = []
    for i in range(len(frames) - 1, 0, -1):
        outer = frames[i]   # caller
        inner = frames[i - 1]  # callee
        edges.append({
            "caller": f"{outer['class']}::{outer['method']}",
            "callee": f"{inner['class']}::{inner['method']}",
            "args": inner["args"],
            "return": "",
        })

    return edges


# ---------------------------------------------------------------------------
# FSM state diagram (T-21, T-50)
# ---------------------------------------------------------------------------

def generate_fsm_diagram(
    enum_name: str,
    states: list[str],
    transitions: list[dict[str, Any]],
    title: Optional[str] = None,
) -> str:
    """
    Generate a Mermaid stateDiagram-v2 from extracted FSM data.

    transitions format:
    [{"from": "Idle", "to": "Reading", "event": "submitRead"}, ...]

    Args:
        enum_name: Name of the state enum (used as diagram title note).
        states: All known state names.
        transitions: List of transition dicts with 'from', 'to', 'event'.
        title: Optional override title.

    Returns:
        Mermaid stateDiagram-v2 string.
    """
    lines = ["stateDiagram-v2"]
    if title or enum_name:
        lines.append(f'    note "FSM: {title or enum_name}"')

    # Initial transition to the first state (heuristic: first enum value)
    if states:
        first = _sanitize_id(states[0])
        lines.append(f"    [*] --> {first}")

    for t in transitions:
        from_s = _sanitize_id(t.get("from", "Unknown"))
        to_s   = _sanitize_id(t.get("to",   "Unknown"))
        event  = t.get("event", "")
        if event:
            lines.append(f"    {from_s} --> {to_s} : {event}")
        else:
            lines.append(f"    {from_s} --> {to_s}")

    return "\n".join(lines)


def extract_fsm_from_source(source_text: str) -> list[dict[str, Any]]:
    """
    Heuristically extract FSM transitions from C++ source text.

    Detects patterns:
      1. switch(state_var) { case StateEnum::X: ... state_var = StateEnum::Y; }
      2. Direct assignment after case label: state_ = State::Writing;

    Returns list of {"enum_name", "states", "transitions"} dicts,
    one per detected switch block.
    """
    # Find enum class definitions
    enum_re = re.compile(
        r"enum\s+(?:class\s+)?(\w+)\s*\{([^}]+)\}",
        re.MULTILINE | re.DOTALL,
    )
    enums: dict[str, list[str]] = {}
    for m in enum_re.finditer(source_text):
        name = m.group(1)
        body = m.group(2)
        values = [v.strip().split("=")[0].strip() for v in body.split(",") if v.strip()]
        values = [v for v in values if re.match(r"^\w+$", v)]
        enums[name] = values

    # Find switch blocks
    switch_re = re.compile(
        r"switch\s*\(\s*(\w+)\s*\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
        re.MULTILINE | re.DOTALL,
    )
    results = []
    for sw_match in switch_re.finditer(source_text):
        switch_var = sw_match.group(1)
        switch_body = sw_match.group(2)

        # Find case labels
        case_re = re.compile(r"case\s+(?:\w+::)?(\w+)\s*:", re.MULTILINE)
        case_labels = [m.group(1) for m in case_re.finditer(switch_body)]

        # Find state assignments within switch body
        assign_re = re.compile(
            r"\b" + re.escape(switch_var) + r"\b\s*=\s*(?:\w+::)?(\w+)\s*;",
            re.MULTILINE,
        )
        assignments = [m.group(1) for m in assign_re.finditer(switch_body)]

        if not case_labels:
            continue

        # Match to a known enum
        matched_enum = None
        for enum_name, enum_vals in enums.items():
            if any(label in enum_vals for label in case_labels):
                matched_enum = enum_name
                break

        transitions = []
        # Build transitions: current case → assigned state
        case_blocks = re.split(r"case\s+(?:\w+::)?(\w+)\s*:", switch_body)
        i = 1
        while i < len(case_blocks) - 1:
            from_state = case_blocks[i]
            block = case_blocks[i + 1] if i + 1 < len(case_blocks) else ""
            for m in assign_re.finditer(block):
                to_state = m.group(1)
                if to_state != from_state:
                    transitions.append({
                        "from": from_state,
                        "to": to_state,
                        "event": "",
                    })
            i += 2

        if matched_enum or case_labels:
            results.append({
                "enum_name": matched_enum or switch_var,
                "states": enums.get(matched_enum, case_labels) if matched_enum else case_labels,
                "transitions": transitions,
            })

    return results


# ---------------------------------------------------------------------------
# File output helpers
# ---------------------------------------------------------------------------

def write_diagram(diagram: str, output_path: str) -> None:
    """Write a Mermaid diagram string to a .mmd file."""
    from pathlib import Path
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(diagram)
        f.write("\n")
    print(f"[mermaid_generator] Wrote diagram to {output_path}")


def generate_all_diagrams(
    entries: list[dict[str, Any]],
    output_dir: str,
    filter_pattern: Optional[str] = None,
    namespace_filter: Optional[str] = None,
) -> dict[str, str]:
    """
    Convenience function: generate both a class diagram and an empty
    sequence diagram placeholder, writing them to output_dir.

    Returns:
        Dict of {"class": path, "sequence": path}
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    class_path = os.path.join(output_dir, "class_diagram.mmd")
    seq_path = os.path.join(output_dir, "sequence_diagram.mmd")

    class_diagram = generate_class_diagram(
        entries,
        filter_pattern=filter_pattern,
        namespace_filter=namespace_filter,
        title="C++ Blueprint Class Diagram",
    )
    write_diagram(class_diagram, class_path)

    seq_diagram = generate_sequence_diagram(
        [],
        title="C++ Blueprint Sequence Diagram (no call graph data)",
    )
    write_diagram(seq_diagram, seq_path)

    return {"class": class_path, "sequence": seq_path}
