"""Minimal local dashboard for the learner platform."""

from __future__ import annotations

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from platform_curriculum import CurriculumService
from platform_progression import ProgressionService
from platform_storage.service import StorageService


class DashboardApp:
    """Render simple server-side HTML views from canonical services."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.curriculum = CurriculumService(self.repository_root)
        self.progression = ProgressionService(
            self.repository_root, curriculum=self.curriculum
        )
        self.storage = StorageService(self.repository_root)

    def render_path(self, path: str, *, user_id: str = "local.user") -> str:
        clean = path.split("?", 1)[0]
        if clean == "/":
            return self._layout("Home", self._home_body(user_id))
        if clean == "/curriculum":
            return self._layout("Curriculum", self._curriculum_body())
        if clean == "/progress":
            return self._layout("Progress", self._progress_body(user_id))
        if clean == "/history":
            return self._layout("History", self._history_body(user_id))
        if clean == "/exam":
            return self._layout("Exam Mode", self._exam_body(user_id))
        if clean.startswith("/module/"):
            return self._layout(
                "Module", self._module_body(unquote(clean.removeprefix("/module/")))
            )
        if clean.startswith("/report/"):
            return self._layout(
                "Report", self._report_body(unquote(clean.removeprefix("/report/")))
            )
        return self._layout(
            "Not Found", "<h1>Not Found</h1><p>Unknown dashboard route.</p>"
        )

    def _layout(self, title: str, body: str) -> str:
        nav = " ".join(
            f'<a href="{href}">{label}</a>'
            for href, label in (
                ("/", "Home"),
                ("/curriculum", "Curriculum"),
                ("/progress", "Progress"),
                ("/history", "History"),
                ("/exam", "Exam"),
            )
        )
        return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Nexus42 - {escape(title)}</title>
  <style>
    :root {{ color-scheme: light; --ink: #16202a; --muted: #5d6b78; --bg: #f5f1e8; --panel: #fffdf8; --line: #d8cfc0; --accent: #0f766e; --accent-2: #b45309; }}
    body {{ margin: 0; font-family: Georgia, 'Times New Roman', serif; color: var(--ink); background: radial-gradient(circle at top right, #f8f5ed, var(--bg)); }}
    header {{ padding: 24px 32px; border-bottom: 1px solid var(--line); background: rgba(255,253,248,0.9); position: sticky; top: 0; backdrop-filter: blur(8px); }}
    header h1 {{ margin: 0 0 8px; font-size: 28px; }}
    nav a {{ margin-right: 14px; color: var(--accent); text-decoration: none; font-weight: 700; }}
    main {{ max-width: 1040px; margin: 0 auto; padding: 24px; }}
    .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 18px; box-shadow: 0 10px 30px rgba(22,32,42,0.06); }}
    .meta {{ color: var(--muted); font-size: 14px; }}
    .badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px; background: #e7f7f5; color: var(--accent); font-size: 12px; margin-right: 6px; }}
    .badge.warn {{ background: #fff1e5; color: var(--accent-2); }}
    ul {{ padding-left: 18px; }}
    code {{ background: #f1ece3; padding: 1px 4px; border-radius: 6px; }}
  </style>
</head>
<body>
  <header>
    <h1>Nexus42 Dashboard</h1>
    <nav>{nav}</nav>
  </header>
  <main>{body}</main>
</body>
</html>"""

    def _home_body(self, user_id: str) -> str:
        snapshot = self.progression.build_snapshot(user_id)
        current = snapshot.get("current_module") or {}
        next_nodes = (
            "".join(
                f"<li><a href='/module/{escape(node['id'])}'>{escape(node['title'])}</a> <span class='meta'>{escape(node['status'])}</span></li>"
                for node in snapshot["unlocked_next_nodes"]
            )
            or "<li>None yet.</li>"
        )
        readiness = (
            "".join(
                f"<li>{escape(item['title'])}: <strong>{'ready' if item['ready'] else 'blocked'}</strong></li>"
                for item in snapshot["exam_readiness_summary"]
            )
            or "<li>No exam nodes.</li>"
        )
        return f"""
<div class=\"grid\">
  <section class=\"panel\">
    <div class=\"meta\">Current module</div>
    <h2>{escape(str(current.get("title", "No active module")))}</h2>
    <p>{escape(str(current.get("summary", "Start from the curriculum view to begin.")))}</p>
  </section>
  <section class=\"panel\">
    <div class=\"meta\">Unlocked next steps</div>
    <ul>{next_nodes}</ul>
  </section>
  <section class=\"panel\">
    <div class=\"meta\">Exam readiness</div>
    <ul>{readiness}</ul>
  </section>
</div>
"""

    def _curriculum_body(self) -> str:
        grouped = self.curriculum.grouped_nodes()
        blocks = []
        for label in ("piscine", "rushes", "exams"):
            items = "".join(
                f"<li><a href='/module/{escape(node.node_id)}'>{escape(node.title)}</a> "
                f"<span class='badge'>{escape(node.status)}</span>"
                f"<span class='meta'>{escape(node.node_id)}</span></li>"
                for node in grouped[label]
            )
            blocks.append(
                f"<section class='panel'><h2>{escape(label.title())}</h2><ul>{items}</ul></section>"
            )
        return f"<div class='grid'>{''.join(blocks)}</div>"

    def _module_body(self, node_id: str) -> str:
        node = self.curriculum.get_node(node_id)
        notices = (
            "".join(f"<li>{escape(item)}</li>" for item in node.notices)
            or "<li>None.</li>"
        )
        exercises = (
            "".join(
                f"<li><code>{escape(item)}</code></li>" for item in node.exercise_ids
            )
            or "<li>None.</li>"
        )
        pools = (
            "".join(f"<li><code>{escape(item)}</code></li>" for item in node.pool_ids)
            or "<li>None.</li>"
        )
        return f"""
<section class=\"panel\">
  <span class=\"badge\">{escape(node.status)}</span>
  <span class=\"badge warn\">{escape(node.grading_mode)}</span>
  <h1>{escape(node.title)}</h1>
  <p>{escape(node.summary)}</p>
  <p class=\"meta\">Difficulty {node.difficulty} · {node.estimated_effort} minutes · prerequisites: {escape(", ".join(node.prerequisites) if node.prerequisites else "none")}</p>
  <h2>Objectives</h2>
  <ul>{"".join(f"<li>{escape(item)}</li>" for item in node.learning_objectives) or "<li>None.</li>"}</ul>
  <h2>Exercises</h2>
  <ul>{exercises}</ul>
  <h2>Pools</h2>
  <ul>{pools}</ul>
  <h2>Notices</h2>
  <ul>{notices}</ul>
</section>
"""

    def _progress_body(self, user_id: str) -> str:
        snapshot = self.progression.build_snapshot(user_id)
        completed = (
            "".join(
                f"<li>{escape(item['title'])} <span class='meta'>{escape(item['id'])}</span></li>"
                for item in snapshot["completed_nodes"]
            )
            or "<li>None yet.</li>"
        )
        notices = (
            "".join(
                f"<li>{escape(item)}</li>"
                for item in snapshot["missing_content_notices"]
            )
            or "<li>None.</li>"
        )
        return f"""
<div class=\"grid\">
  <section class=\"panel\"><h2>Completed Nodes</h2><ul>{completed}</ul></section>
  <section class=\"panel\"><h2>Missing Content Notices</h2><ul>{notices}</ul></section>
</div>
"""

    def _history_body(self, user_id: str) -> str:
        attempts = self.progression.attempt_history(user_id)
        reports = self.progression.report_history(user_id)
        attempt_items = (
            "".join(
                f"<li>{escape(str(item['created_at']))} - {escape(str(item['exercise_id']))} - {'PASS' if item['passed'] else 'FAIL'}</li>"
                for item in attempts
            )
            or "<li>No graded attempts yet.</li>"
        )
        report_items = (
            "".join(
                f"<li><a href='/report/{escape(str(item['report_id']))}'>{escape(str(item['report_id']))}</a> - {escape(str(item['summary']))}</li>"
                for item in reports
            )
            or "<li>No reports yet.</li>"
        )
        return f"""
<div class=\"grid\">
  <section class=\"panel\"><h2>Attempts</h2><ul>{attempt_items}</ul></section>
  <section class=\"panel\"><h2>Reports</h2><ul>{report_items}</ul></section>
</div>
"""

    def _exam_body(self, user_id: str) -> str:
        summary = self.progression.build_snapshot(user_id)["exam_readiness_summary"]
        items = []
        for item in summary:
            blockers = (
                "<br>".join(escape(blocker) for blocker in item["blockers"]) or "ready"
            )
            items.append(
                f"<li><strong>{escape(item['title'])}</strong> - {'ready' if item['ready'] else 'blocked'}<div class='meta'>{blockers}</div></li>"
            )
        joined = "".join(items) or "<li>No exam nodes available.</li>"
        return f"<section class='panel'><h2>Exam Tracks</h2><ul>{joined}</ul><p class='meta'>Use <code>grademe exam start</code> from the CLI to begin a writable exam workspace.</p></section>"

    def _report_body(self, report_id: str) -> str:
        relative = f"runtime/reports/{report_id}.yml"
        report = self.storage.read_yaml(relative)
        evaluation = dict(report.get("evaluation", {}))
        feedback = dict(report.get("feedback", {}))
        return f"""
<section class=\"panel\">
  <h1>{escape(report_id)}</h1>
  <p><strong>Exercise:</strong> {escape(str(report.get("exercise_id", "")))}</p>
  <p><strong>Mode:</strong> {escape(str(report.get("mode", "")))}</p>
  <p><strong>Score:</strong> {escape(str(evaluation.get("normalized_score", 0.0)))}</p>
  <p><strong>Failure class:</strong> {escape(str(evaluation.get("failure_class", "unknown")))}</p>
  <p><strong>Summary:</strong> {escape(str(feedback.get("summary", "")))}</p>
</section>
"""


def _platform_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="platform-dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8420, help="Bind port.")
    parser.add_argument(
        "--once", help="Render one route to stdout and exit, for example /curriculum."
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    app = DashboardApp(_platform_root())
    if args.once:
        print(app.render_path(args.once))
        return 0

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            payload = app.render_path(self.path).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return None

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"platform-dashboard: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
