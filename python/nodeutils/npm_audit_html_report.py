#!/usr/bin/env python3
"""Generate a self-contained HTML report from npm audit JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Set, Tuple


SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "moderate": 2,
    "low": 3,
    "info": 4,
    "unknown": 5,
}

ROOT_SECTIONS = ("dependencies", "devDependencies", "optionalDependencies")
LOCK_DEPENDENCY_FIELDS = ("dependencies", "optionalDependencies", "devDependencies", "peerDependencies")


def load_json(path: Path) -> Dict[str, Any]:
    """Load and parse a JSON file as a dictionary."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Expected a file path, got: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed reading file {path}: {exc}") from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"Expected top-level JSON object in {path}")

    return parsed


def parse_top_level_roots(package_json: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Build a map of top-level package roots from package.json sections."""
    roots: Dict[str, Dict[str, str]] = {}
    for section in ROOT_SECTIONS:
        section_obj = package_json.get(section)
        if not isinstance(section_obj, dict):
            continue
        for name, requested_version in section_obj.items():
            if not isinstance(name, str):
                continue
            if not isinstance(requested_version, str):
                requested_version = str(requested_version)
            roots[name] = {
                "name": name,
                "section": section,
                "requested_version": requested_version,
            }
    return roots


def _lock_path_to_name(lock_path: str, lock_pkg: Dict[str, Any]) -> Optional[str]:
    """Infer package name for a lockfile path entry."""
    lock_name = lock_pkg.get("name")
    if isinstance(lock_name, str) and lock_name:
        return lock_name

    if lock_path == "":
        return "__root__"

    parts = [part for part in lock_path.split("/") if part and part != "node_modules"]
    if not parts:
        return None

    if len(parts) >= 2 and parts[-2].startswith("@"):
        return f"{parts[-2]}/{parts[-1]}"
    return parts[-1]


def _parent_lock_path(lock_path: str) -> Optional[str]:
    """Find the parent lockfile path for a packages key path."""
    if lock_path == "":
        return None

    parts = lock_path.split("/")
    if "node_modules" not in parts:
        return ""

    nm_idx = [idx for idx, part in enumerate(parts) if part == "node_modules"]
    last_nm = nm_idx[-1]

    if last_nm == 0:
        return ""

    parent_parts = parts[:last_nm]
    return "/".join(parent_parts)


def _build_graph_from_packages(packages_obj: Dict[str, Any]) -> Dict[str, Any]:
    node_name_by_path: Dict[str, str] = {}
    paths_by_name: Dict[str, Set[str]] = defaultdict(set)

    for lock_path, lock_pkg in packages_obj.items():
        if not isinstance(lock_path, str) or not isinstance(lock_pkg, dict):
            continue
        name = _lock_path_to_name(lock_path, lock_pkg)
        if not name:
            continue
        node_name_by_path[lock_path] = name
        paths_by_name[name].add(lock_path)

    parents_of: Dict[str, Set[str]] = defaultdict(set)
    children_of: Dict[str, Set[str]] = defaultdict(set)

    for lock_path in node_name_by_path:
        parent = _parent_lock_path(lock_path)
        if parent is None:
            continue
        if parent not in node_name_by_path:
            parent = "" if "" in node_name_by_path else None
        if parent is None:
            continue

        children_of[parent].add(lock_path)
        parents_of[lock_path].add(parent)

    for lock_path, lock_pkg in packages_obj.items():
        if not isinstance(lock_path, str) or not isinstance(lock_pkg, dict):
            continue
        if lock_path not in node_name_by_path:
            continue

        for field in LOCK_DEPENDENCY_FIELDS:
            dep_obj = lock_pkg.get(field)
            if not isinstance(dep_obj, dict):
                continue
            for dep_name in dep_obj:
                if not isinstance(dep_name, str):
                    continue
                dep_path = _resolve_dependency_path(lock_path, dep_name, node_name_by_path)
                if dep_path is None or dep_path == lock_path:
                    continue
                children_of[lock_path].add(dep_path)
                parents_of[dep_path].add(lock_path)

    return {
        "node_name_by_path": node_name_by_path,
        "paths_by_name": {name: sorted(paths) for name, paths in paths_by_name.items()},
        "parents_of": {node: sorted(parents) for node, parents in parents_of.items()},
        "children_of": {node: sorted(children) for node, children in children_of.items()},
    }


def _dependency_lookup_bases(lock_path: str) -> List[str]:
    """Return package paths to inspect while resolving a dependency name."""
    bases: List[str] = []
    current: Optional[str] = lock_path
    while current is not None:
        bases.append(current)
        current = _parent_lock_path(current)
    return bases


def _resolve_dependency_path(
    lock_path: str,
    dependency_name: str,
    node_name_by_path: Dict[str, str],
) -> Optional[str]:
    """Resolve a package-lock dependency name to the installed package path."""
    for base in _dependency_lookup_bases(lock_path):
        candidate = f"{base}/node_modules/{dependency_name}" if base else f"node_modules/{dependency_name}"
        if candidate in node_name_by_path:
            return candidate
    return None


def _build_graph_from_legacy_dependencies(package_lock: Dict[str, Any]) -> Dict[str, Any]:
    node_name_by_path: Dict[str, str] = {"": "__root__"}
    parents_of: Dict[str, Set[str]] = defaultdict(set)
    children_of: Dict[str, Set[str]] = defaultdict(set)
    paths_by_name: Dict[str, Set[str]] = defaultdict(set)

    counter = 0

    def add_node(name: str, parent_path: str) -> str:
        nonlocal counter
        counter += 1
        path = f"legacy:{name}:{counter}"
        node_name_by_path[path] = name
        paths_by_name[name].add(path)
        parents_of[path].add(parent_path)
        children_of[parent_path].add(path)
        return path

    def walk(dep_obj: Dict[str, Any], parent_path: str) -> None:
        if not isinstance(dep_obj, dict):
            return
        for dep_name, dep_data in dep_obj.items():
            if not isinstance(dep_name, str) or not isinstance(dep_data, dict):
                continue
            current_path = add_node(dep_name, parent_path)
            walk(dep_data.get("dependencies", {}), current_path)

    walk(package_lock.get("dependencies", {}), "")

    return {
        "node_name_by_path": node_name_by_path,
        "paths_by_name": {name: sorted(paths) for name, paths in paths_by_name.items()},
        "parents_of": {node: sorted(parents) for node, parents in parents_of.items()},
        "children_of": {node: sorted(children) for node, children in children_of.items()},
    }


def build_dependency_graph(package_lock: Dict[str, Any]) -> Dict[str, Any]:
    """Build dependency graph structures from package-lock.json."""
    packages_obj = package_lock.get("packages")
    if isinstance(packages_obj, dict) and packages_obj:
        return _build_graph_from_packages(packages_obj)
    return _build_graph_from_legacy_dependencies(package_lock)


def _extract_titles_and_cwes(via: Any) -> Tuple[List[str], List[str]]:
    titles: List[str] = []
    cwes: Set[str] = set()

    if isinstance(via, list):
        via_entries = via
    elif via is None:
        via_entries = []
    else:
        via_entries = [via]

    for entry in via_entries:
        if isinstance(entry, str):
            titles.append(entry)
            continue
        if not isinstance(entry, dict):
            continue

        title = entry.get("title") or entry.get("name") or entry.get("source")
        if title is not None:
            titles.append(str(title))

        cwe_value = entry.get("cwe")
        if isinstance(cwe_value, list):
            for cwe_item in cwe_value:
                if cwe_item:
                    cwes.add(str(cwe_item))
        elif cwe_value:
            cwes.add(str(cwe_value))

    return titles, sorted(cwes)


def _normalize_fix_available(fix_available: Any) -> str:
    if isinstance(fix_available, bool):
        return "yes" if fix_available else "no"
    if isinstance(fix_available, dict):
        name = fix_available.get("name")
        version = fix_available.get("version")
        is_semver_major = fix_available.get("isSemVerMajor")
        if name and version:
            base = f"{name}@{version}"
            if is_semver_major:
                return f"{base} (semver-major)"
            return base
        return "yes"
    if fix_available is None:
        return "no"
    return str(fix_available)


def normalize_audit(audit_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize npm audit data to a row-oriented internal structure."""
    vulnerabilities = audit_json.get("vulnerabilities", {})
    if not isinstance(vulnerabilities, dict):
        return []

    rows: List[Dict[str, Any]] = []

    for package_name, vuln_obj in vulnerabilities.items():
        if not isinstance(vuln_obj, dict):
            continue

        resolved_package_name = vuln_obj.get("name") if isinstance(vuln_obj.get("name"), str) else package_name
        if not isinstance(resolved_package_name, str):
            resolved_package_name = str(resolved_package_name)

        severity = vuln_obj.get("severity") if isinstance(vuln_obj.get("severity"), str) else "unknown"
        via_titles, cwes = _extract_titles_and_cwes(vuln_obj.get("via"))

        title = via_titles[0] if via_titles else f"Vulnerability in {resolved_package_name}"

        nodes = vuln_obj.get("nodes") if isinstance(vuln_obj.get("nodes"), list) else []
        effects = vuln_obj.get("effects") if isinstance(vuln_obj.get("effects"), list) else []

        rows.append(
            {
                "package_name": resolved_package_name,
                "title": title,
                "severity": severity,
                "vulnerable_versions": vuln_obj.get("range"),
                "fix_available": _normalize_fix_available(vuln_obj.get("fixAvailable")),
                "is_direct": bool(vuln_obj.get("isDirect")),
                "via": [str(item) for item in via_titles],
                "cwes": cwes,
                "effects": [str(item) for item in effects],
                "nodes": [str(item) for item in nodes],
                "tied_roots": [],
                "reachable_from_dev": False,
                "reachable_from_prod": False,
                "dependency_chain_sample": [],
                "reachability": "unknown",
            }
        )

    rows.sort(key=lambda row: (SEVERITY_ORDER.get(row["severity"], 99), row["package_name"], row["title"]))
    return rows


def _find_roots_and_chain_for_package(
    package_name: str,
    graph: Dict[str, Any],
    roots: Dict[str, Dict[str, str]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    parents_of = graph.get("parents_of", {})
    node_name_by_path = graph.get("node_name_by_path", {})
    paths_by_name = graph.get("paths_by_name", {})

    start_paths = paths_by_name.get(package_name, [])
    if not start_paths:
        return [], []

    discovered_roots: Dict[str, Dict[str, Any]] = {}
    best_chain: List[str] = []

    queue: Deque[str] = deque(start_paths)
    seen: Set[str] = set(start_paths)
    prev: Dict[str, Optional[str]] = {path: None for path in start_paths}

    while queue:
        node = queue.popleft()
        node_name = node_name_by_path.get(node)
        if node_name in roots:
            root_info = roots[node_name]
            chain: List[str] = []
            walk = node
            while walk is not None:
                walk_name = node_name_by_path.get(walk)
                if walk_name and walk_name != "__root__":
                    chain.append(walk_name)
                walk = prev.get(walk)

            current_root = discovered_roots.get(root_info["name"])
            if current_root is None or len(chain) < len(current_root.get("chain", [])):
                enriched_root = dict(root_info)
                enriched_root["chain"] = chain
                discovered_roots[root_info["name"]] = enriched_root
            if not best_chain or len(chain) < len(best_chain):
                best_chain = chain

        for parent in parents_of.get(node, []):
            if parent in seen:
                continue
            seen.add(parent)
            prev[parent] = node
            queue.append(parent)

    tied_roots = sorted(discovered_roots.values(), key=lambda item: item["name"])
    return tied_roots, best_chain


def enrich_rows_with_roots_and_paths(
    rows: List[Dict[str, Any]],
    graph: Dict[str, Any],
    roots: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Attach root-dependency reachability details to each normalized row."""
    for row in rows:
        tied_roots, chain = _find_roots_and_chain_for_package(row["package_name"], graph, roots)
        row["tied_roots"] = tied_roots
        row["dependency_chain_sample"] = chain

        sections = {entry.get("section", "unknown") for entry in tied_roots}
        row["reachable_from_prod"] = "dependencies" in sections or "optionalDependencies" in sections
        row["reachable_from_dev"] = "devDependencies" in sections

        if row["reachable_from_prod"] and row["reachable_from_dev"]:
            row["reachability"] = "prod+dev"
        elif row["reachable_from_prod"]:
            row["reachability"] = "prod"
        elif row["reachable_from_dev"]:
            row["reachability"] = "dev-only"
        else:
            row["reachability"] = "unknown"

    return rows


def _build_metadata(rows: List[Dict[str, Any]], audit_json: Dict[str, Any]) -> Dict[str, Any]:
    severity_counts = Counter(row.get("severity", "unknown") for row in rows)
    metadata = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "total": len(rows),
        "distinct_packages": len({row.get("package_name") for row in rows}),
        "severity_counts": {
            "critical": severity_counts.get("critical", 0),
            "high": severity_counts.get("high", 0),
            "moderate": severity_counts.get("moderate", 0),
            "low": severity_counts.get("low", 0),
            "info": severity_counts.get("info", 0),
            "unknown": severity_counts.get("unknown", 0),
        },
        "audit_metadata": audit_json.get("metadata", {}),
    }
    return metadata


def render_html(rows: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
    """Render the self-contained report HTML."""
    rows_json = json.dumps(rows, ensure_ascii=False)
    metadata_json = json.dumps(metadata, ensure_ascii=False)

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>npm audit HTML report</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #111827;
      --panel: #f8fafc;
      --surface: #ffffff;
      --surface-2: #f1f5f9;
      --text: #111827;
      --muted: #64748b;
      --border: #dbe3ef;
      --border-strong: #b7c3d3;
      --accent: #0f766e;
      --accent-soft: #ccfbf1;
      --critical: #b91c1c;
      --high: #c2410c;
      --moderate: #b45309;
      --low: #2563eb;
      --unknown: #475569;
      --shadow: 0 18px 40px rgba(15, 23, 42, 0.14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, var(--bg) 0, var(--bg) 260px, #eef2f7 260px);
      color: var(--text);
    }}
    .container {{ padding: 28px; max-width: 1500px; margin: 0 auto; }}
    .hero {{ color: #f8fafc; margin-bottom: 22px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; font-weight: 750; letter-spacing: 0; }}
    .meta {{ color: #cbd5e1; font-size: 14px; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05); }}
    .card .label {{ color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: 0; text-transform: uppercase; }}
    .card .value {{ font-size: 26px; font-weight: 760; margin-top: 6px; }}
    .report-panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow); overflow: hidden; }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      padding: 14px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
    }}
    .controls input[type=\"text\"] {{ flex: 2 1 360px; }}
    .controls select {{ flex: 1 1 170px; }}
    input[type=\"text\"], select {{
      width: 100%;
      border: 1px solid var(--border-strong);
      background: #ffffff;
      color: var(--text);
      padding: 9px 10px;
      border-radius: 6px;
      min-height: 38px;
    }}
    label {{ display: inline-flex; align-items: center; gap: 6px; min-height: 38px; font-size: 13px; color: var(--muted); white-space: nowrap; }}
    button {{
      border: 1px solid var(--border-strong);
      background: #ffffff;
      color: var(--text);
      border-radius: 6px;
      padding: 9px 11px;
      cursor: pointer;
      min-height: 38px;
      margin-left: auto;
    }}
    button:hover {{ border-color: var(--accent); color: var(--accent); }}
    .count-line {{ padding: 10px 14px; color: var(--muted); border-bottom: 1px solid var(--border); background: var(--surface-2); }}
    .table-shell {{ overflow-x: auto; }}
    table {{ width: 100%; min-width: 1080px; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--border); vertical-align: top; padding: 12px; text-align: left; }}
    th {{ background: #e8eef6; color: #334155; position: sticky; top: 0; z-index: 1; font-size: 11px; text-transform: uppercase; letter-spacing: 0; }}
    tbody tr:hover {{ background: #f8fafc; }}
    .title-cell {{ min-width: 290px; }}
    .vuln-title {{ font-weight: 700; line-height: 1.35; }}
    .package-stack {{ display: grid; gap: 6px; }}
    .package-name {{ font-weight: 700; }}
    .root-link-list {{ display: grid; gap: 8px; min-width: 280px; }}
    .root-link {{
      border: 1px solid var(--border);
      border-left: 4px solid var(--accent);
      border-radius: 8px;
      padding: 8px 10px;
      background: #fbfdff;
    }}
    .root-main {{ display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }}
    .root-chain {{ margin-top: 6px; color: var(--muted); line-height: 1.45; overflow-wrap: anywhere; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      line-height: 1.6;
      margin: 2px 4px 2px 0;
      border: 1px solid var(--border);
      background: var(--surface-2);
      color: #334155;
      white-space: nowrap;
    }}
    .pill-accent {{ background: var(--accent-soft); border-color: #99f6e4; color: #115e59; }}
    .sev-critical {{ background: #fee2e2; border-color: #fecaca; color: var(--critical); font-weight: 700; }}
    .sev-high {{ background: #ffedd5; border-color: #fed7aa; color: var(--high); font-weight: 700; }}
    .sev-moderate {{ background: #fef3c7; border-color: #fde68a; color: var(--moderate); font-weight: 700; }}
    .sev-low {{ background: #dbeafe; border-color: #bfdbfe; color: var(--low); font-weight: 700; }}
    .sev-info, .sev-unknown {{ background: #e2e8f0; border-color: #cbd5e1; color: var(--unknown); font-weight: 700; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .small {{ font-size: 12px; color: var(--muted); }}
    .nowrap {{ white-space: nowrap; }}
    @media (max-width: 720px) {{
      .container {{ padding: 18px; }}
      .summary-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .controls input[type=\"text\"], .controls select, .controls button {{ flex-basis: 100%; }}
      .controls button {{ margin-left: 0; }}
    }}
  </style>
</head>
<body>
  <div class=\"container\">
    <div class=\"hero\">
      <h1>npm audit HTML report</h1>
      <div class=\"meta\" id=\"meta\"></div>
    </div>

    <div class=\"summary-grid\" id=\"summary\"></div>

    <div class=\"report-panel\">
      <div class=\"controls\">
        <input id=\"search\" type=\"text\" placeholder=\"Search title, vulnerable package, package.json package, advisory, chain\" />
        <select id=\"severity\">
          <option value=\"\">All severities</option>
          <option>critical</option>
          <option>high</option>
          <option>moderate</option>
          <option>low</option>
          <option>info</option>
          <option>unknown</option>
        </select>
        <select id=\"rootSection\">
          <option value=\"\">All package.json sections</option>
          <option>dependencies</option>
          <option>devDependencies</option>
          <option>optionalDependencies</option>
          <option>unknown</option>
        </select>
        <label><input id=\"fixOnly\" type=\"checkbox\" /> fix available</label>
        <label><input id=\"devOnly\" type=\"checkbox\" /> dev-only</label>
        <label><input id=\"prodReachable\" type=\"checkbox\" /> prod-reachable</label>
        <button id=\"clearBtn\" type=\"button\">Clear filters</button>
      </div>

      <div class=\"count-line\" id=\"filteredCount\"></div>

      <div class=\"table-shell\">
        <table>
          <thead>
            <tr>
              <th>Vulnerability</th>
              <th>Vulnerable package</th>
              <th>Package.json link</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Fix</th>
              <th>CWEs</th>
            </tr>
          </thead>
          <tbody id=\"rows\"></tbody>
        </table>
      </div>
    </div>
  </div>

<script>
const rows = {rows_json};
const metadata = {metadata_json};

function escapeHtml(value) {{
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}}

function severityClass(sev) {{
  const safe = (sev || "unknown").toLowerCase();
  return "sev-" + (['critical','high','moderate','low','info','unknown'].includes(safe) ? safe : 'unknown');
}}

function buildSummary() {{
  const summary = document.getElementById('summary');
  const c = metadata.severity_counts || {{}};
  const cards = [
    ['Critical', c.critical || 0, 'sev-critical'],
    ['High', c.high || 0, 'sev-high'],
    ['Moderate', c.moderate || 0, 'sev-moderate'],
    ['Low', c.low || 0, 'sev-low'],
    ['Total Vulns', metadata.total || 0, ''],
    ['Distinct Packages', metadata.distinct_packages || 0, ''],
  ];
  summary.innerHTML = cards.map(([label, value, klass]) => `<div class=\"card\"><div class=\"label\">${{escapeHtml(label)}}</div><div class=\"value\"><span class=\"pill ${{klass}}\">${{escapeHtml(value)}}</span></div></div>`).join('');
}}

function selectedValues() {{
  return {{
    q: document.getElementById('search').value.trim().toLowerCase(),
    severity: document.getElementById('severity').value,
    rootSection: document.getElementById('rootSection').value,
    fixOnly: document.getElementById('fixOnly').checked,
    devOnly: document.getElementById('devOnly').checked,
    prodReachable: document.getElementById('prodReachable').checked,
  }};
}}

function rowMatches(row, state) {{
  if (state.severity && row.severity !== state.severity) return false;

  const rootSections = new Set((row.tied_roots || []).map(r => r.section || 'unknown'));
  if (state.rootSection) {{
    if (rootSections.size === 0) {{
      if (state.rootSection !== 'unknown') return false;
    }} else if (!rootSections.has(state.rootSection)) {{
      return false;
    }}
  }}

  if (state.fixOnly && String(row.fix_available).toLowerCase() === 'no') return false;
  if (state.devOnly && !(row.reachable_from_dev === true && row.reachable_from_prod === false)) return false;
  if (state.prodReachable && row.reachable_from_prod !== true) return false;

  if (state.q) {{
    const hay = [
      row.title,
      row.package_name,
      (row.via || []).join(' '),
      (row.cwes || []).join(' '),
      (row.dependency_chain_sample || []).join(' -> '),
      (row.tied_roots || []).map(r => (r.chain || []).join(' -> ')).join(' '),
      (row.tied_roots || []).map(r => `${{r.name}} ${{r.section}} ${{r.requested_version}}`).join(' ')
    ].join(' ').toLowerCase();
    if (!hay.includes(state.q)) return false;
  }}

  return true;
}}

function formatFix(fixAvailable) {{
  const value = String(fixAvailable || 'no');
  const normalized = value.toLowerCase();
  const klass = normalized === 'no' ? '' : 'pill-accent';
  return `<span class=\"pill ${{klass}}\">${{escapeHtml(value)}}</span>`;
}}

function formatRootLinks(row) {{
  const roots = row.tied_roots || [];
  if (roots.length === 0) {{
    const chain = (row.dependency_chain_sample || []).length
      ? escapeHtml(row.dependency_chain_sample.join(' -> '))
      : 'No package.json root found in package-lock';
    return `<div class=\"root-link-list\"><div class=\"root-link\"><div class=\"small\">${{chain}}</div></div></div>`;
  }}

  return `<div class=\"root-link-list\">${{roots.map((root) => {{
    const chain = (root.chain || row.dependency_chain_sample || []).length
      ? escapeHtml((root.chain || row.dependency_chain_sample).join(' -> '))
      : escapeHtml(`${{root.name}} -> ${{row.package_name}}`);
    return `<div class=\"root-link\">
      <div class=\"root-main\">
        <span class=\"pill pill-accent mono\">${{escapeHtml(root.name)}}</span>
        <span class=\"pill mono\">${{escapeHtml(root.requested_version || 'version unknown')}}</span>
        <span class=\"pill\">${{escapeHtml(root.section || 'unknown')}}</span>
      </div>
      <div class=\"root-chain mono\">${{chain}}</div>
    </div>`;
  }}).join('')}}</div>`;
}}

function renderRows() {{
  const state = selectedValues();
  const filtered = rows.filter(r => rowMatches(r, state));

  const tbody = document.getElementById('rows');
  tbody.innerHTML = filtered.map((row) => {{
    const cwes = (row.cwes || []).length ? (row.cwes || []).map(cwe => `<span class=\"pill mono\">${{escapeHtml(cwe)}}</span>`).join('') : '<span class=\"small\">-</span>';
    const via = (row.via || []).slice(1, 3).join(' | ');
    const vulnerableRange = row.vulnerable_versions ? `<div class=\"small mono\">range: ${{escapeHtml(row.vulnerable_versions)}}</div>` : '';

    return `<tr>
      <td class=\"title-cell\">
        <div class=\"vuln-title\">${{escapeHtml(row.title)}}</div>
        ${{via ? `<div class=\"small\">${{escapeHtml(via)}}</div>` : ''}}
      </td>
      <td>
        <div class=\"package-stack\">
          <span class=\"package-name mono\">${{escapeHtml(row.package_name)}}</span>
          ${{vulnerableRange}}
        </div>
      </td>
      <td>${{formatRootLinks(row)}}</td>
      <td><span class=\"pill ${{severityClass(row.severity)}}\">${{escapeHtml(row.severity || 'unknown')}}</span></td>
      <td class=\"nowrap\">
        ${{row.is_direct ? '<span class=\"pill pill-accent\">direct</span>' : '<span class=\"pill\">indirect</span>'}}
        <span class=\"pill\">${{escapeHtml(row.reachability || 'unknown')}}</span>
      </td>
      <td>${{formatFix(row.fix_available)}}</td>
      <td>${{cwes}}</td>
    </tr>`;
  }}).join('');

  document.getElementById('filteredCount').textContent = `Showing ${{filtered.length}} of ${{rows.length}} vulnerabilities`;
}}

function attach() {{
  ['search','severity','rootSection','fixOnly','devOnly','prodReachable'].forEach((id) => {{
    document.getElementById(id).addEventListener('input', renderRows);
    document.getElementById(id).addEventListener('change', renderRows);
  }});
  document.getElementById('clearBtn').addEventListener('click', () => {{
    document.getElementById('search').value = '';
    document.getElementById('severity').value = '';
    document.getElementById('rootSection').value = '';
    document.getElementById('fixOnly').checked = false;
    document.getElementById('devOnly').checked = false;
    document.getElementById('prodReachable').checked = false;
    renderRows();
  }});

  document.getElementById('meta').textContent =
    `Generated: ${{metadata.generated_at || 'unknown'}} | Total vulnerabilities: ${{metadata.total || 0}}`;

  buildSummary();
  renderRows();
}}

attach();
</script>
</body>
</html>
"""


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a filterable HTML report from npm audit JSON")
    parser.add_argument("--audit", required=True, help="Path to npm audit --json output file")
    parser.add_argument("--package-json", default="package.json", help="Path to package.json")
    parser.add_argument("--package-lock", default="package-lock.json", help="Path to package-lock.json")
    parser.add_argument("--output", default="audit-report.html", help="Output HTML path")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    audit_path = Path(args.audit)
    package_json_path = Path(args.package_json)
    package_lock_path = Path(args.package_lock)
    output_path = Path(args.output)

    try:
        audit_json = load_json(audit_path)
        package_json = load_json(package_json_path)
        package_lock = load_json(package_lock_path)

        roots = parse_top_level_roots(package_json)
        graph = build_dependency_graph(package_lock)
        rows = normalize_audit(audit_json)
        rows = enrich_rows_with_roots_and_paths(rows, graph, roots)

        metadata = _build_metadata(rows, audit_json)
        html = render_html(rows, metadata)

        output_path.write_text(html, encoding="utf-8")
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error writing output file {output_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Generated npm audit HTML report: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
