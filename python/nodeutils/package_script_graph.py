#!/usr/bin/env python3
"""Render npm package-script relationships without executing any scripts."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


SHELL_CONTROL_CHARS = frozenset(";&|()\n")
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
NPM_OPTION_VALUES = {
    "--cache",
    "--prefix",
    "--registry",
    "--userconfig",
    "--workspace",
    "-w",
}


@dataclass(frozen=True, order=True)
class Edge:
    """A relationship where invoking source causes target to run."""

    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class ScriptGraph:
    scripts: Mapping[str, str]
    edges: Tuple[Edge, ...]
    missing_targets: Tuple[str, ...]
    cycles: Tuple[Tuple[str, ...], ...]


def load_scripts(path: Path) -> Dict[str, str]:
    """Load and validate the scripts object from package.json."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Expected a file path, got: {path}")

    try:
        package_data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Failed reading file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(package_data, dict):
        raise ValueError(f"Expected top-level JSON object in {path}")

    scripts_data = package_data.get("scripts", {})
    if scripts_data is None:
        return {}
    if not isinstance(scripts_data, dict):
        raise ValueError(f"Expected 'scripts' to be an object in {path}")

    scripts: Dict[str, str] = {}
    for name, command in scripts_data.items():
        if not isinstance(name, str) or not isinstance(command, str):
            raise ValueError(f"Expected every script name and command to be a string in {path}")
        scripts[name] = command
    return scripts


def _shell_segments(command: str) -> List[List[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.commenters = ""
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True

    segments: List[List[str]] = []
    current: List[str] = []
    for token in lexer:
        if token and all(character in SHELL_CONTROL_CHARS for character in token):
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def _is_npm_command(token: str) -> bool:
    executable = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return executable in {"npm", "npm.cmd", "npm.exe"}


def _command_index(tokens: Sequence[str]) -> int:
    """Return the index of a directly invoked command after common wrappers."""
    index = 0
    while index < len(tokens) and ASSIGNMENT_RE.match(tokens[index]):
        index += 1

    while index < len(tokens) and tokens[index] in {"command", "builtin", "exec"}:
        index += 1

    if index < len(tokens) and tokens[index] in {"env", "cross-env", "cross-env-shell"}:
        index += 1
        while index < len(tokens):
            token = tokens[index]
            if ASSIGNMENT_RE.match(token):
                index += 1
                continue
            if token == "--":
                index += 1
                break
            if token.startswith("-"):
                index += 1
                continue
            break
    return index


def _skip_options(tokens: Sequence[str], index: int) -> int:
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            return index + 1
        if not token.startswith("-") or token == "-":
            return index
        option = token.split("=", 1)[0]
        index += 1
        if option in NPM_OPTION_VALUES and "=" not in token and index < len(tokens):
            index += 1
    return index


def _npm_target(tokens: Sequence[str]) -> Optional[str]:
    command_index = _command_index(tokens)
    if command_index >= len(tokens) or not _is_npm_command(tokens[command_index]):
        return None

    index = _skip_options(tokens, command_index + 1)
    if index >= len(tokens):
        return None

    subcommand = tokens[index].lower()
    if subcommand in {"test", "t", "tst"}:
        return "test"
    if subcommand == "start":
        return "start"
    if subcommand not in {"run", "run-script"}:
        return None

    index = _skip_options(tokens, index + 1)
    if index >= len(tokens):
        return None
    return tokens[index]


def find_npm_targets(command: str) -> Tuple[str, ...]:
    """Find script targets in direct npm invocations within a shell command."""
    try:
        segments = _shell_segments(command)
    except ValueError as exc:
        raise ValueError(f"Invalid shell quoting: {exc}") from exc

    targets = {_npm_target(segment) for segment in segments}
    return tuple(sorted(target for target in targets if target is not None))


def _find_cycles(nodes: Iterable[str], edges: Iterable[Edge]) -> Tuple[Tuple[str, ...], ...]:
    adjacency: Dict[str, Set[str]] = {node: set() for node in nodes}
    for edge in edges:
        if edge.target in adjacency:
            adjacency.setdefault(edge.source, set()).add(edge.target)

    index = 0
    indices: Dict[str, int] = {}
    lowlinks: Dict[str, int] = {}
    stack: List[str] = []
    on_stack: Set[str] = set()
    components: List[Tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(adjacency[node]):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])

        if lowlinks[node] != indices[node]:
            return

        component: List[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break

        ordered = tuple(sorted(component))
        if len(ordered) > 1 or node in adjacency[node]:
            components.append(ordered)

    for node in sorted(adjacency):
        if node not in indices:
            visit(node)

    return tuple(sorted(components))


def build_graph(scripts: Mapping[str, str]) -> ScriptGraph:
    edges: Set[Edge] = set()

    for script_name in sorted(scripts):
        command = scripts[script_name]
        try:
            targets = find_npm_targets(command)
        except ValueError as exc:
            raise ValueError(f"Script {script_name!r} has {exc}") from exc
        for target in targets:
            edges.add(Edge(script_name, target, "npm"))

        pre_script = f"pre{script_name}"
        post_script = f"post{script_name}"
        if pre_script in scripts:
            edges.add(Edge(script_name, pre_script, "pre"))
        if post_script in scripts:
            edges.add(Edge(script_name, post_script, "post"))

    ordered_edges = tuple(sorted(edges))
    missing = tuple(sorted({edge.target for edge in ordered_edges if edge.target not in scripts}))
    cycles = _find_cycles(scripts, ordered_edges)
    return ScriptGraph(dict(scripts), ordered_edges, missing, cycles)


def _mermaid_label(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def render_mermaid(graph: ScriptGraph) -> str:
    node_names = sorted(set(graph.scripts) | set(graph.missing_targets))
    node_ids = {name: f"script_{index}" for index, name in enumerate(node_names)}
    cycle_nodes = {name for cycle in graph.cycles for name in cycle}

    lines = ["flowchart LR"]
    if not node_names:
        lines.append("    %% No npm scripts found")
        return "\n".join(lines) + "\n"

    for name in node_names:
        suffix = " (missing)" if name in graph.missing_targets else ""
        lines.append(f'    {node_ids[name]}["{_mermaid_label(name + suffix)}"]')

    for edge in graph.edges:
        source = node_ids[edge.source]
        target = node_ids[edge.target]
        if edge.kind == "npm":
            lines.append(f"    {source} -->|npm run| {target}")
        else:
            lines.append(f"    {source} -. {edge.kind} .-> {target}")

    lines.append("    classDef missing fill:#fff4e5,stroke:#c77700,stroke-dasharray:5 5")
    lines.append("    classDef cycle fill:#ffe8e8,stroke:#b42318,stroke-width:2px")
    if graph.missing_targets:
        missing_ids = ",".join(node_ids[name] for name in graph.missing_targets)
        lines.append(f"    class {missing_ids} missing")
    if cycle_nodes:
        cycle_ids = ",".join(node_ids[name] for name in sorted(cycle_nodes))
        lines.append(f"    class {cycle_ids} cycle")
    for cycle in graph.cycles:
        lines.append(f"    %% Cycle: {', '.join(cycle)}")
    return "\n".join(lines) + "\n"


def _dot_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_dot(graph: ScriptGraph) -> str:
    node_names = sorted(set(graph.scripts) | set(graph.missing_targets))
    node_ids = {name: f"script_{index}" for index, name in enumerate(node_names)}
    cycle_nodes = {name for cycle in graph.cycles for name in cycle}

    lines = ["digraph npm_scripts {", "  rankdir=LR;"]
    if not node_names:
        lines.append("  // No npm scripts found")

    for name in node_names:
        attributes = [f'label="{_dot_label(name)}"']
        if name in graph.missing_targets:
            attributes.extend(['xlabel="missing"', 'color="#c77700"', 'style="dashed"'])
        if name in cycle_nodes:
            attributes.extend(['fillcolor="#ffe8e8"', 'color="#b42318"', 'style="filled"'])
        lines.append(f"  {node_ids[name]} [{', '.join(attributes)}];")

    for edge in graph.edges:
        attributes = [f'label="{edge.kind if edge.kind != "npm" else "npm run"}"']
        if edge.kind != "npm":
            attributes.append('style="dashed"')
        lines.append(
            f"  {node_ids[edge.source]} -> {node_ids[edge.target]} "
            f"[{', '.join(attributes)}];"
        )
    for cycle in graph.cycles:
        lines.append(f"  // Cycle: {', '.join(_dot_label(name) for name in cycle)}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def diagnostics(graph: ScriptGraph) -> Tuple[str, ...]:
    messages: List[str] = []
    for target in graph.missing_targets:
        sources = sorted(edge.source for edge in graph.edges if edge.target == target)
        messages.append(f"Missing script target {target!r}, referenced by: {', '.join(sources)}")
    for cycle in graph.cycles:
        if len(cycle) == 1:
            messages.append(f"Cycle detected: {cycle[0]} references itself")
        else:
            messages.append(f"Cycle detected among scripts: {', '.join(cycle)}")
    return tuple(messages)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render npm package-script dependencies without running scripts"
    )
    parser.add_argument(
        "package_json",
        nargs="?",
        default="package.json",
        help="package.json path (default: package.json)",
    )
    parser.add_argument(
        "--format",
        choices=("mermaid", "dot"),
        default="mermaid",
        help="graph output format (default: mermaid)",
    )
    parser.add_argument("--output", help="write the graph to this file instead of stdout")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    package_path = Path(args.package_json)

    try:
        graph = build_graph(load_scripts(package_path))
        output = render_mermaid(graph) if args.format == "mermaid" else render_dot(graph)
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for message in diagnostics(graph):
        print(f"Warning: {message}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
