#!/usr/bin/env python3
"""Print HTML preview of conversations fetched from INTERCEPTOR_API.
Useful to validate what the Streamlit component should render (server-side).
"""

import os
import requests
import html as _html

API = os.environ.get("INTERCEPTOR_API", "http://192.168.15.2:8503")
colors = [
    "#a8dadc",
    "#ffd6a5",
    "#caffbf",
    "#bdb2ff",
    "#ffc6ff",
    "#ffdbe7",
    "#ffe8d6",
    "#f8d49f",
]


def fetch():
    r = requests.get(f"{API}/interceptor/conversations/active", timeout=5)
    r.raise_for_status()
    return r.json().get("conversations", [])


def build_html(convs):
    parts = []
    for i, c in enumerate(convs):
        p = c.get("participants") or []
        frm = p[0] if len(p) > 0 else "agent1"
        to = p[1] if len(p) > 1 else (p[0] if p else "all")
        # try to fetch last message content from messages endpoint
        preview = ""
        cid = c.get("id") or c.get("conversation_id")
        if cid:
            try:
                mr = requests.get(
                    f"{API}/interceptor/conversations/{cid}/messages", timeout=3
                )
                mr.raise_for_status()
                msgs = mr.json().get("messages") or []
                if msgs:
                    m = msgs[-1]
                    if isinstance(m, dict):
                        preview = m.get("content") or m.get("message") or ""
                    else:
                        preview = getattr(m, "content", str(m))
            except Exception:
                preview = ""
        text = (
            f"{_html.escape(frm)} -> {_html.escape(to)}: {_html.escape(str(preview))}"
        )
        color = colors[i % len(colors)]
        parts.append(
            f'<div style="background:{color};padding:10px;margin:6px 0;border-radius:6px;">{text}</div>'
        )
    body = "\n".join(parts) if parts else "<div>Nenhuma conversa ativa</div>"
    return f"<html><body>{body}</body></html>"


def main():
    convs = fetch()
    html = build_html(convs)
    print(html)


if __name__ == "__main__":
    main()
