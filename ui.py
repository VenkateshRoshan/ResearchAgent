"""
ui.py
─────
Tiny browser UI for myResearchAgent.

It serves a single chat page that:
- sends a prompt to `api.py`
- streams orchestrator steps as "thinking"
- renders the final assistant answer as markdown

Usage:
  python ui.py
  python ui.py --api-base http://127.0.0.1:8000 --port 8501
"""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def build_html(api_base: str) -> str:
    api_base_json = json.dumps(api_base.rstrip("/"))
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>myResearchAgent UI</title>
  <script src=\"https://cdn.jsdelivr.net/npm/marked/marked.min.js\"></script>
  <script src=\"https://cdn.jsdelivr.net/npm/dompurify@3.2.6/dist/purify.min.js\"></script>
  <script type=\"module\">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    window.__mermaid = mermaid;
    mermaid.initialize({{ startOnLoad: false, securityLevel: 'loose', theme: 'neutral' }});
  </script>
  <style>
    :root {{
      --bg: #f7f3ee;
      --panel: #fffdf9;
      --panel-2: #f3ede5;
      --border: #ddd2c6;
      --text: #1f1b16;
      --muted: #6d6257;
      --accent: #9b6b3d;
      --accent-soft: #efe2d4;
      --ok: #1f7a4c;
      --warn: #8a5a00;
      --err: #a52222;
      --shadow: 0 18px 50px rgba(57, 41, 24, 0.08);
      --radius: 18px;
      --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: linear-gradient(180deg, #f9f6f1 0%, #f3ede5 100%);
      color: var(--text);
      font-family: var(--sans);
    }}

    .app {{
      max-width: 1100px;
      margin: 0 auto;
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 18px;
      padding: 18px;
    }}

    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 18px 22px;
      background: rgba(255, 253, 249, 0.82);
      border: 1px solid rgba(221, 210, 198, 0.85);
      backdrop-filter: blur(12px);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }}

    .title h1 {{
      margin: 0;
      font-size: 1.2rem;
      font-weight: 700;
    }}

    .title p {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.95rem;
    }}

    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      border-radius: 999px;
      background: var(--panel-2);
      color: var(--muted);
      font-size: 0.9rem;
      border: 1px solid var(--border);
      white-space: nowrap;
    }}

    .status-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--warn);
      box-shadow: 0 0 0 4px rgba(155, 107, 61, 0.12);
    }}

    .status-pill.ok .status-dot {{ background: var(--ok); }}
    .status-pill.err .status-dot {{ background: var(--err); }}

    .chat {{
      display: flex;
      flex-direction: column;
      gap: 16px;
      overflow-y: auto;
      padding-right: 4px;
    }}

    .hero {{
      padding: 28px;
      background: rgba(255, 253, 249, 0.86);
      border: 1px solid rgba(221, 210, 198, 0.9);
      border-radius: 24px;
      box-shadow: var(--shadow);
    }}

    .hero h2 {{ margin: 0 0 10px; }}
    .hero p {{ margin: 0; color: var(--muted); line-height: 1.6; }}

    .message {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 18px;
      border-radius: 22px;
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
      background: var(--panel);
    }}

    .message.user {{
      margin-left: auto;
      max-width: min(78%, 720px);
      background: linear-gradient(180deg, #f8ecdf 0%, #f3e3d2 100%);
      border-color: #e4ceb7;
    }}

    .message.assistant {{
      max-width: min(90%, 920px);
      background: linear-gradient(180deg, #fffdf9 0%, #fbf7f2 100%);
    }}

    .message-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      font-size: 0.95rem;
    }}

    .message-role {{ font-weight: 700; }}
    .message-meta {{ color: var(--muted); font-size: 0.88rem; }}

    .bubble {{
      white-space: pre-wrap;
      line-height: 1.65;
    }}

    .thinking-panel {{
      border: 1px solid var(--border);
      background: #f8f3ec;
      border-radius: 16px;
      overflow: hidden;
    }}

    .thinking-panel summary {{
      list-style: none;
      cursor: pointer;
      padding: 14px 16px;
      font-weight: 600;
      color: var(--text);
      background: rgba(155, 107, 61, 0.06);
    }}

    .thinking-panel summary::-webkit-details-marker {{ display: none; }}

    .timeline {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 12px;
    }}

    .step-card {{
      border: 1px solid #e7dacd;
      background: #fffdf9;
      border-radius: 14px;
      padding: 12px 14px;
    }}

    .step-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
      font-size: 0.86rem;
      color: var(--muted);
    }}

    .step-title {{
      font-weight: 600;
      color: var(--text);
      margin-bottom: 6px;
    }}

    .step-body {{
      color: var(--muted);
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
    }}

    .markdown {{
      padding: 4px 2px 2px;
    }}

    .markdown h1, .markdown h2, .markdown h3, .markdown h4 {{
      margin-top: 1.25em;
      margin-bottom: 0.55em;
    }}

    .markdown p, .markdown li {{ line-height: 1.7; }}

    .markdown pre {{
      overflow-x: auto;
      background: #1f1f1f;
      color: #f8f8f2;
      padding: 16px;
      border-radius: 14px;
      font-family: var(--mono);
      font-size: 0.92rem;
    }}

    .markdown code {{
      font-family: var(--mono);
      font-size: 0.92em;
      background: rgba(31, 27, 22, 0.06);
      padding: 0.12em 0.34em;
      border-radius: 6px;
    }}

    .markdown pre code {{
      background: transparent;
      padding: 0;
      border-radius: 0;
    }}

    .markdown blockquote {{
      margin: 1em 0;
      padding: 0.1em 1em;
      border-left: 4px solid #d2b89d;
      color: #5d5146;
      background: #fbf6f0;
      border-radius: 0 12px 12px 0;
    }}

    .mermaid-wrap {{
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 12px;
      overflow-x: auto;
      margin: 14px 0;
    }}

    .result-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 0.88rem;
      padding-top: 6px;
    }}

    .chip {{
      display: inline-flex;
      align-items: center;
      padding: 7px 10px;
      border-radius: 999px;
      background: var(--panel-2);
      border: 1px solid var(--border);
    }}

    .composer {{
      padding: 14px;
      border-radius: 24px;
      background: rgba(255, 253, 249, 0.88);
      border: 1px solid rgba(221, 210, 198, 0.9);
      box-shadow: var(--shadow);
    }}

    .composer form {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: end;
    }}

    textarea {{
      width: 100%;
      min-height: 88px;
      max-height: 260px;
      resize: vertical;
      padding: 16px 18px;
      border-radius: 18px;
      border: 1px solid var(--border);
      background: #fffdf9;
      color: var(--text);
      font: inherit;
      outline: none;
    }}

    textarea:focus {{ border-color: #c7a381; box-shadow: 0 0 0 4px rgba(199, 163, 129, 0.16); }}

    button {{
      border: 0;
      border-radius: 16px;
      padding: 16px 18px;
      background: linear-gradient(180deg, #a76f3c 0%, #8d5d31 100%);
      color: white;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      min-width: 128px;
    }}

    button:disabled {{
      opacity: 0.7;
      cursor: progress;
    }}

    .footer-note {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.85rem;
    }}

    @media (max-width: 768px) {{
      .app {{ padding: 12px; }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .composer form {{ grid-template-columns: 1fr; }}
      .message.user, .message.assistant {{ max-width: 100%; }}
    }}
  </style>
</head>
<body>
  <div class=\"app\">
    <header class=\"topbar\">
      <div class=\"title\">
        <h1>myResearchAgent</h1>
        <p>Markdown-first research chat with streamed thinking steps.</p>
      </div>
      <div id=\"api-status\" class=\"status-pill\">
        <span class=\"status-dot\"></span>
        <span>Checking API…</span>
      </div>
    </header>

    <main id=\"chat\" class=\"chat\">
      <section class=\"hero\">
        <h2>Ask for research</h2>
        <p>
          The assistant will show the orchestrator's agent calls as thinking steps,
          then render the final markdown report directly in the chat.
        </p>
      </section>
    </main>

    <section class=\"composer\">
      <form id=\"composer-form\">
        <textarea id=\"query\" placeholder=\"Ask for a research report, architecture summary, comparison, or deep dive…\"></textarea>
        <button id=\"send\" type=\"submit\">Send</button>
      </form>
      <div class=\"footer-note\">Press Enter to send. Use Shift+Enter for a newline.</div>
    </section>
  </div>

  <script>
    const API_BASE = {api_base_json};
    const chat = document.getElementById('chat');
    const form = document.getElementById('composer-form');
    const textarea = document.getElementById('query');
    const sendButton = document.getElementById('send');
    const apiStatus = document.getElementById('api-status');

    function setApiStatus(kind, text) {{
      apiStatus.className = 'status-pill' + (kind ? ' ' + kind : '');
      apiStatus.querySelector('span:last-child').textContent = text;
    }}

    async function checkHealth() {{
      try {{
        const response = await fetch(`${{API_BASE}}/health`);
        if (!response.ok) throw new Error('API not reachable');
        setApiStatus('ok', `API connected · ${{API_BASE}}`);
      }} catch (error) {{
        setApiStatus('err', `API unavailable · ${{API_BASE}}`);
      }}
    }}

    function escapeHtml(text) {{
      return text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function markdownToHtml(markdown) {{
      if (window.marked) {{
        const rawHtml = window.marked.parse(markdown, {{ gfm: true, breaks: true }});
        if (window.DOMPurify) {{
          return window.DOMPurify.sanitize(rawHtml);
        }}
        return rawHtml;
      }}
      return `<pre>${{escapeHtml(markdown)}}</pre>`;
    }}

    async function renderMermaidBlocks(container) {{
      const mermaid = window.__mermaid;
      if (!mermaid) return;

      const blocks = container.querySelectorAll('pre code.language-mermaid');
      let index = 0;
      for (const block of blocks) {{
        const source = block.textContent || '';
        const wrapper = document.createElement('div');
        wrapper.className = 'mermaid-wrap';

        try {{
          const id = `mermaid-${{Date.now()}}-${{index++}}`;
          const result = await mermaid.render(id, source);
          wrapper.innerHTML = result.svg;
          block.parentElement.replaceWith(wrapper);
        }} catch (error) {{
          wrapper.innerHTML = `<pre>${{escapeHtml(source)}}</pre>`;
          block.parentElement.replaceWith(wrapper);
        }}
      }}
    }}

    function scrollToBottom() {{
      requestAnimationFrame(() => {{
        window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
      }});
    }}

    function addUserMessage(text) {{
      const article = document.createElement('article');
      article.className = 'message user';
      article.innerHTML = `
        <div class="message-header">
          <span class="message-role">You</span>
          <span class="message-meta">Prompt</span>
        </div>
        <div class="bubble"></div>
      `;
      article.querySelector('.bubble').textContent = text;
      chat.appendChild(article);
      scrollToBottom();
    }}

    function addAssistantShell() {{
      const article = document.createElement('article');
      article.className = 'message assistant';
      article.innerHTML = `
        <div class="message-header">
          <span class="message-role">Research Agent</span>
          <span class="message-meta">Streaming response</span>
        </div>
        <details class="thinking-panel" open>
          <summary>Thinking steps</summary>
          <div class="timeline"></div>
        </details>
        <div class="markdown"></div>
        <div class="result-meta"></div>
      `;
      chat.appendChild(article);
      scrollToBottom();
      return {{
        root: article,
        timeline: article.querySelector('.timeline'),
        markdown: article.querySelector('.markdown'),
        meta: article.querySelector('.result-meta'),
        details: article.querySelector('.thinking-panel'),
      }};
    }}

    function appendStep(shell, payload) {{
      const card = document.createElement('div');
      card.className = 'step-card';
      const phase = payload.phase === 'observation' ? 'Observation' : 'Action';
      const title = payload.agent_label || payload.label || 'Step';
      const body = payload.preview || payload.detail || payload.summary || '';
      card.innerHTML = `
        <div class="step-top">
          <span>${{phase}}</span>
          <span>step ${{payload.step ?? '—'}}</span>
        </div>
        <div class="step-title">${{escapeHtml(title)}}</div>
        <div class="step-body">${{escapeHtml(body)}}</div>
      `;
      shell.timeline.appendChild(card);
      scrollToBottom();
    }}

    function appendStatus(shell, payload) {{
      const card = document.createElement('div');
      card.className = 'step-card';
      card.innerHTML = `
        <div class="step-top">
          <span>Status</span>
          <span>system</span>
        </div>
        <div class="step-title">${{escapeHtml(payload.label || 'Status')}}</div>
        <div class="step-body">${{escapeHtml(payload.detail || '')}}</div>
      `;
      shell.timeline.appendChild(card);
      scrollToBottom();
    }}

    async function showFinalMarkdown(shell, markdown) {{
      shell.markdown.innerHTML = markdownToHtml(markdown);
      await renderMermaidBlocks(shell.markdown);
      scrollToBottom();
    }}

    function setResultMeta(shell, items) {{
      shell.meta.innerHTML = '';
      items.filter(Boolean).forEach((item) => {{
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.textContent = item;
        shell.meta.appendChild(chip);
      }});
    }}

    function appendError(shell, message) {{
      shell.markdown.innerHTML = `<blockquote><strong>Error:</strong> ${{escapeHtml(message)}}</blockquote>`;
      setResultMeta(shell, ['Request failed']);
      scrollToBottom();
    }}

    async function startChat(query) {{
      addUserMessage(query);
      const shell = addAssistantShell();
      sendButton.disabled = true;
      setApiStatus('', 'Sending request…');

      try {{
        const startResponse = await fetch(`${{API_BASE}}/chat/start`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ query }}),
        }});

        const startPayload = await startResponse.json();
        if (!startResponse.ok) {{
          throw new Error(startPayload.error || 'Failed to start chat job.');
        }}

        setApiStatus('ok', `Streaming from ${{API_BASE}}`);
        const stream = new EventSource(`${{API_BASE}}/stream/${{startPayload.job_id}}`);

        stream.addEventListener('status', (event) => {{
          appendStatus(shell, JSON.parse(event.data));
        }});

        stream.addEventListener('thinking', (event) => {{
          appendStep(shell, JSON.parse(event.data));
        }});

        stream.addEventListener('final', async (event) => {{
          const payload = JSON.parse(event.data);
          await showFinalMarkdown(shell, payload.content || '');
          shell.details.open = false;
        }});

        stream.addEventListener('done', (event) => {{
          const payload = JSON.parse(event.data);
          const saveLabel = payload.saved_to ? `Saved to ${{payload.saved_to}}` : '';
          const timeLabel = payload.elapsed_sec ? `${{payload.elapsed_sec}}s` : '';
          setResultMeta(shell, [saveLabel, timeLabel]);
          setApiStatus('ok', `Completed · ${{API_BASE}}`);
          sendButton.disabled = false;
          stream.close();
        }});

        stream.addEventListener('error', (event) => {{
          try {{
            const payload = event.data ? JSON.parse(event.data) : {{ message: 'Stream error.' }};
            appendError(shell, payload.message || 'Stream error.');
          }} catch {{
            appendError(shell, 'Stream error.');
          }}
          setApiStatus('err', `API error · ${{API_BASE}}`);
          sendButton.disabled = false;
          stream.close();
        }});

        stream.onerror = () => {{
          if (sendButton.disabled) {{
            setApiStatus('err', `Connection interrupted · ${{API_BASE}}`);
            sendButton.disabled = false;
          }}
        }};
      }} catch (error) {{
        appendError(shell, error.message || 'Request failed.');
        setApiStatus('err', `API unavailable · ${{API_BASE}}`);
        sendButton.disabled = false;
      }} finally {{
        textarea.focus();
      }}
    }}

    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      const query = textarea.value.trim();
      if (!query || sendButton.disabled) return;
      textarea.value = '';
      await startChat(query);
    }});

    textarea.addEventListener('keydown', (event) => {{
      if (event.key === 'Enter' && !event.shiftKey) {{
        event.preventDefault();
        form.requestSubmit();
      }}
    }});

    textarea.focus();
    checkHealth();
  </script>
</body>
</html>
"""


class UIHandler(BaseHTTPRequestHandler):
    server_version = "ResearchAgentUI/1.0"
    api_base = "http://127.0.0.1:8000"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path not in {"/", "/index.html"}:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        payload = build_html(self.api_base).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def build_server(host: str, port: int, api_base: str) -> ThreadingHTTPServer:
    handler = type("ConfiguredUIHandler", (UIHandler,), {"api_base": api_base})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the myResearchAgent browser UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8501, help="Bind port")
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8000",
        help="Base URL for the API server",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not auto-open the browser",
    )
    args = parser.parse_args()

    server = build_server(args.host, args.port, args.api_base)
    url = f"http://{args.host}:{args.port}"
    print(f"UI running at {url}")
    print(f"Using API at {args.api_base}")

    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down UI...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
