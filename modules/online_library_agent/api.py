from __future__ import annotations

import html
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .config import load_config
from .models import AskRequest
from .planner import OnlineLibraryPlanner

app = FastAPI(title="Online Library NLQ Agent")


GUIDED_QUESTIONS: dict[str, list[str]] = {
    "User Questions": [
        "List library users.",
        "Show pending user approval requests.",
        "Show user subscription records.",
    ],
    "Reading Progress": [
        "Show reading progress records.",
        "Show user bookshelf records.",
    ],
    "Library Content": [
        "List available books and resources.",
        "List authors.",
        "List categories.",
        "List tags.",
    ],
    "Subscription": [
        "Show subscription tiers.",
        "Show subscription rules.",
    ],
}


@app.get("/health")
def health() -> dict[str, Any]:
    """Return agent configuration details useful during local POC testing."""

    config = load_config()
    return {
        "status": "ok",
        "mcp_url": config.mcp_url,
        "ollama_base_url": config.ollama_base_url,
        "ollama_model": config.ollama_model,
    }


@app.get("/tools")
async def tools() -> dict[str, Any]:
    """Expose the MCP tools the agent can currently see."""

    planner = OnlineLibraryPlanner()
    tool_list = await planner.list_tools()
    return {
        "count": len(tool_list),
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in tool_list
        ],
    }


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    """Send browser users directly to the guided ask page."""

    return render_ask_page()


@app.get("/ask", response_class=HTMLResponse)
def ask_page() -> HTMLResponse:
    """Render the guided NLQ form for demos."""

    return render_ask_page()


@app.post("/ask")
async def ask(request: Request) -> Response:
    """Handle JSON API calls and browser form submissions through one flow."""

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        ask_request = AskRequest.model_validate(payload)
        result = await _process_question(ask_request)
        return JSONResponse(result)

    form = await request.form()
    ask_request = AskRequest(
        question=str(form.get("question", "")).strip(),
        limit=int(form.get("limit", 10)),
        offset=int(form.get("offset", 0)),
        include_raw=str(form.get("include_raw", "true")).lower() == "true",
    )
    result = await _process_question(ask_request)
    return render_ask_page(result)


async def _process_question(ask_request: AskRequest) -> dict[str, Any]:
    """Delegate NLQ processing to the planner so API and HTML stay consistent."""

    planner = OnlineLibraryPlanner()
    return await planner.answer_question(
        question=ask_request.question,
        limit=ask_request.limit,
        offset=ask_request.offset,
        include_raw=ask_request.include_raw,
    )


def render_ask_page(result: dict[str, Any] | None = None) -> HTMLResponse:
    """Render a compact HTML page with guided questions and POC diagnostics."""

    result_html = _result_html(result) if result else ""
    sections = "\n".join(_question_section(title, questions) for title, questions in GUIDED_QUESTIONS.items())
    html_text = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Online Library Agent</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f6f8fb;
      color: #1f2937;
    }}
    main {{
      max-width: 980px;
      margin: 32px auto;
      padding: 0 20px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 16px;
    }}
    section {{
      background: #ffffff;
      border: 1px solid #d7dee8;
      border-radius: 8px;
      padding: 18px;
    }}
    label {{
      display: block;
      font-weight: 700;
      margin: 12px 0 6px;
    }}
    select, input {{
      box-sizing: border-box;
      width: 100%;
      padding: 10px;
      border: 1px solid #b9c4d0;
      border-radius: 6px;
      font-size: 15px;
    }}
    .row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    button {{
      margin-top: 14px;
      padding: 10px 14px;
      border: 0;
      border-radius: 6px;
      background: #1f6feb;
      color: #ffffff;
      font-size: 15px;
      cursor: pointer;
    }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #0f172a;
      color: #e5e7eb;
      padding: 14px;
      border-radius: 8px;
    }}
    .result-table-wrap {{
      margin-top: 14px;
      border: 1px solid #b9c4d0;
      border-radius: 8px;
      overflow: auto;
      background: #ffffff;
    }}
    table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 14px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid #e2e8f0;
      border-right: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      background: #eef3f8;
      font-weight: 700;
      color: #263344;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    th:last-child, td:last-child {{
      border-right: 0;
    }}
    .bullet-cell {{
      width: 32px;
      text-align: center;
      color: #1f6feb;
      font-weight: 700;
    }}
    .answer-block {{
      margin-top: 16px;
      padding: 12px 14px;
      border: 1px solid #d7dee8;
      border-radius: 8px;
      background: #f8fafc;
    }}
    .unsupported-block {{
      margin-top: 16px;
      padding: 14px 16px;
      border: 1px solid #f0c36d;
      border-radius: 8px;
      background: #fff8e6;
      color: #5f4300;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Online Library Agent</h1>
    <p>Ask questions about online library users, resources, authors, categories, tags, reading progress, subscriptions, and approvals.</p>
    <div class="grid">
      {sections}
      {_open_question_section()}
    </div>
    {result_html}
  </main>
</body>
</html>
"""
    return HTMLResponse(html_text)


def _question_section(title: str, questions: list[str]) -> str:
    options = "\n".join(f'<option value="{html.escape(question)}">{html.escape(question)}</option>' for question in questions)
    return f"""
<section>
  <h2>{html.escape(title)}</h2>
  <form method="post" action="/ask">
    <label>Question</label>
    <select name="question">{options}</select>
    {_common_controls()}
    <button type="submit">Ask Agent</button>
  </form>
</section>
"""


def _open_question_section() -> str:
    return f"""
<section>
  <h2>Ask Anything About The Online Library</h2>
  <form method="post" action="/ask">
    <label>Question</label>
    <input name="question" placeholder="Example: List active users" required>
    {_common_controls()}
    <button type="submit">Ask Agent</button>
  </form>
</section>
"""


def _common_controls() -> str:
    return """
<div class="row">
  <div>
    <label>Limit</label>
    <input name="limit" type="number" min="1" max="100" value="10">
  </div>
  <div>
    <label>Offset</label>
    <input name="offset" type="number" min="0" value="0">
  </div>
</div>
<input type="hidden" name="include_raw" value="true">
"""


def _result_html(result: dict[str, Any]) -> str:
    answer = html.escape(str(result.get("answer", "")))
    question = html.escape(str(result.get("question", "")))
    selected_tool = html.escape(str(result.get("selected_tool", "")))
    debug = html.escape(_to_pretty_json(result.get("debug", {})))
    raw = html.escape(_to_pretty_json(result.get("raw_tool_result", {})))
    is_unsupported = result.get("result_type") == "unsupported_question"
    table_html = "" if is_unsupported else _result_table_html(result.get("raw_tool_result"))
    tool_line = (
        "<p><strong>Tool used:</strong> No matching tool</p>"
        if is_unsupported
        else f"<p><strong>Tool used:</strong> {selected_tool}</p>"
    )
    answer_class = "unsupported-block" if is_unsupported else "answer-block"
    return f"""
<section>
  <h2>Result</h2>
  {tool_line}
  <p><strong>NLQ:</strong> {question}</p>
  {table_html}
  <div class="{answer_class}">{answer}</div>
  <h3>Developer Diagnostics</h3>
  <pre>{debug}</pre>
  <h3>Raw MCP Tool Result</h3>
  <pre>{raw}</pre>
</section>
"""


def _result_table_html(raw_tool_result: Any) -> str:
    """Render MCP rows in a read-only table for the browser POC."""

    if not isinstance(raw_tool_result, dict):
        return "<p>No table data returned.</p>"
    rows = raw_tool_result.get("rows")
    if not isinstance(rows, list) or not rows:
        return "<p>No rows returned.</p>"
    if not all(isinstance(row, dict) for row in rows):
        return "<p>The tool result did not contain table-shaped rows.</p>"

    columns: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in columns:
                columns.append(key)

    header_cells = '<th class="bullet-cell">#</th>' + "".join(
        f"<th>{html.escape(column)}</th>" for column in columns
    )
    body_rows = []
    for row in rows:
        cells = ['<td class="bullet-cell">&bull;</td>']
        cells.extend(f"<td>{_format_cell(row.get(column))}</td>" for column in columns)
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""
<h3>Data</h3>
<div class="result-table-wrap">
  <table aria-label="MCP tool result rows">
    <thead><tr>{header_cells}</tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
</div>
"""


def _format_cell(value: Any) -> str:
    """Format a table cell without making the result editable."""

    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return html.escape(_to_pretty_json(value))
    return html.escape(str(value))


def _to_pretty_json(value: Any) -> str:
    import json

    return json.dumps(value, indent=2, default=str)
