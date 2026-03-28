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

    return {
        "node_name_by_path": node_name_by_path,
        "paths_by_name": {name: sorted(paths) for name, paths in paths_by_name.items()},
        "parents_of": {node: sorted(parents) for node, parents in parents_of.items()},
        "children_of": {node: sorted(children) for node, children in children_of.items()},
    }


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
) -> Tuple[List[Dict[str, str]], List[str]]:
    parents_of = graph.get("parents_of", {})
    node_name_by_path = graph.get("node_name_by_path", {})
    paths_by_name = graph.get("paths_by_name", {})

    start_paths = paths_by_name.get(package_name, [])
    if not start_paths:
        return [], []

    discovered_roots: Dict[str, Dict[str, str]] = {}
    best_chain: List[str] = []

    queue: Deque[str] = deque(start_paths)
    seen: Set[str] = set(start_paths)
    prev: Dict[str, Optional[str]] = {path: None for path in start_paths}

    while queue:
        node = queue.popleft()
        node_name = node_name_by_path.get(node)
        if node_name in roots:
            root_info = roots[node_name]
            discovered_roots[root_info["name"]] = root_info
            if not best_chain:
                chain: List[str] = []
                walk = node
                while walk is not None:
                    walk_name = node_name_by_path.get(walk)
                    if walk_name and walk_name != "__root__":
                        chain.append(walk_name)
                    walk = prev.get(walk)
                best_chain = list(reversed(chain))

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
      --bg: #0f172a;
      --card: #111827;
      --muted: #cbd5e1;
      --border: #334155;
      --table-head: #1e293b;
      --good: #16a34a;
      --warn: #d97706;
      --bad: #dc2626;
      --text: #e2e8f0;
    }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
    .container {{ padding: 20px; max-width: 1400px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .meta {{ color: var(--muted); margin-bottom: 16px; font-size: 14px; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 10px; margin-bottom: 16px; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 10px; }}
    .card .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .card .value {{ font-size: 22px; margin-top: 4px; }}
    .controls {{ display: grid; grid-template-columns: 2fr 1fr 1fr auto auto auto auto; gap: 8px; align-items: center; margin-bottom: 12px; }}
    input[type=\"text\"], select {{ width: 100%; border: 1px solid var(--border); background: var(--card); color: var(--text); padding: 8px; border-radius: 6px; }}
    label {{ font-size: 13px; color: var(--muted); white-space: nowrap; }}
    button {{ border: 1px solid var(--border); background: transparent; color: var(--text); border-radius: 6px; padding: 8px 10px; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--border); vertical-align: top; padding: 8px; text-align: left; }}
    th {{ background: var(--table-head); position: sticky; top: 0; z-index: 1; }}
    .pill {{ display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 11px; margin: 2px 4px 2px 0; border: 1px solid var(--border); }}
    .sev-critical {{ background: #7f1d1d; }}
    .sev-high {{ background: #991b1b; }}
    .sev-moderate {{ background: #9a3412; }}
    .sev-low {{ background: #1d4ed8; }}
    .sev-info, .sev-unknown {{ background: #374151; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .small {{ font-size: 12px; color: var(--muted); }}
    .count-line {{ margin-bottom: 8px; color: var(--muted); }}
    .nowrap {{ white-space: nowrap; }}
  </style>
</head>
<body>
  <div class=\"container\">
    <h1>npm audit HTML report</h1>
    <div class=\"meta\" id=\"meta\"></div>

    <div class=\"summary-grid\" id=\"summary\"></div>

    <div class=\"controls\">
      <input id=\"search\" type=\"text\" placeholder=\"Search title, package, roots, advisories, chain\" />
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
        <option value=\"\">All root sections</option>
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

    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Vulnerable Package</th>
          <th>Severity</th>
          <th>Root Package(s)</th>
          <th>Root Section(s)</th>
          <th>Direct/Indirect</th>
          <th>Fix Available</th>
          <th>Reachability</th>
          <th>CWEs</th>
          <th>Dependency Chain</th>
        </tr>
      </thead>
      <tbody id=\"rows\"></tbody>
    </table>
  </div>

<script>
const rows = {rows_json};
const metadata = {metadata_json};

function escapeHtml(value) {{
  return String(value || "")
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
    ['Critical', c.critical || 0],
    ['High', c.high || 0],
    ['Moderate', c.moderate || 0],
    ['Low', c.low || 0],
    ['Total Vulns', metadata.total || 0],
    ['Distinct Packages', metadata.distinct_packages || 0],
  ];
  summary.innerHTML = cards.map(([label, value]) => `<div class=\"card\"><div class=\"label\">${{escapeHtml(label)}}</div><div class=\"value\">${{escapeHtml(value)}}</div></div>`).join('');
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
      (row.tied_roots || []).map(r => `${{r.name}} ${{r.section}} ${{r.requested_version}}`).join(' ')
    ].join(' ').toLowerCase();
    if (!hay.includes(state.q)) return false;
  }}

  return true;
}}

function renderRows() {{
  const state = selectedValues();
  const filtered = rows.filter(r => rowMatches(r, state));

  const tbody = document.getElementById('rows');
  tbody.innerHTML = filtered.map((row) => {{
    const roots = (row.tied_roots || []).map((root) => `<span class=\"pill mono\" title=\"requested: ${{escapeHtml(root.requested_version || '')}}\">${{escapeHtml(root.name)}}</span>`).join('') || '<span class=\"small\">unknown</span>';
    const rootSections = (() => {{
      const sections = Array.from(new Set((row.tied_roots || []).map(root => root.section || 'unknown')));
      if (sections.length === 0) return '<span class=\"small\">unknown</span>';
      return sections.map(section => `<span class=\"pill\">${{escapeHtml(section)}}</span>`).join('');
    }})();
    const cwes = (row.cwes || []).length ? (row.cwes || []).map(cwe => `<span class=\"pill mono\">${{escapeHtml(cwe)}}</span>`).join('') : '<span class=\"small\">-</span>';
    const chain = (row.dependency_chain_sample || []).length ? `<span class=\"mono\">${{escapeHtml(row.dependency_chain_sample.join(' -> '))}}</span>` : '<span class=\"small\">unresolved</span>';

    return `<tr>
      <td>
        <div>${{escapeHtml(row.title)}}</div>
        <div class=\"small\">${{escapeHtml((row.via || []).slice(1, 3).join(' | '))}}</div>
      </td>
      <td class=\"mono\">${{escapeHtml(row.package_name)}}</td>
      <td><span class=\"pill ${{severityClass(row.severity)}}\">${{escapeHtml(row.severity || 'unknown')}}</span></td>
      <td>${{roots}}</td>
      <td>${{rootSections}}</td>
      <td class=\"nowrap\">${{row.is_direct ? '<span class="pill">direct</span>' : '<span class="pill">indirect</span>'}}</td>
      <td>${{String(row.fix_available).toLowerCase() === 'no' ? '<span class="pill">no</span>' : '<span class="pill">' + escapeHtml(row.fix_available) + '</span>'}}</td>
      <td><span class=\"pill\">${{escapeHtml(row.reachability || 'unknown')}}</span></td>
      <td>${{cwes}}</td>
      <td>${{chain}}</td>
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
