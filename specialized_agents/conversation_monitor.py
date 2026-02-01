#!/usr/bin/env python3
import streamlit as st
import os
import requests
from datetime import datetime

"""
Simple conversation monitor (minimal)

Displays a read-only text area containing conversation summaries fetched
from the interceptor API. Sidebar allows overriding `INTERCEPTOR_API`
and sending a simple test message.
"""

INTERCEPTOR_API = os.environ.get("INTERCEPTOR_API", "http://192.168.15.2:8503")

st.set_page_config(page_title="Conversations (simple)", layout="wide")

with st.sidebar:
    user_api = st.text_input(
        "Interceptor API",
        value=INTERCEPTOR_API,
        help="URL do serviço interceptor (ex: http://192.168.15.2:8503)",
    )
    if user_api:
        INTERCEPTOR_API = user_api.rstrip("/")

    if st.button("Send interceptor test message"):
        try:
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            msg = f"STREAMLIT_SIMPLE_TEST_{ts}"
            r = requests.post(
                f"{INTERCEPTOR_API}/communication/test",
                data={"message": msg},
                timeout=5,
            )
            if r.ok:
                st.success("Test message sent: " + msg)
            else:
                st.error(f"Failed: {r.status_code} {r.text}")
        except Exception as e:
            st.error(f"Error sending test message: {e}")


def fetch_conversations(api_base: str):
    try:
        r = requests.get(f"{api_base}/interceptor/conversations/active", timeout=5)
        r.raise_for_status()
        data = r.json()
        return data.get("conversations", [])
    except Exception as e:
        return {"error": str(e)}


def format_conversations(convs):
    if isinstance(convs, dict) and convs.get("error"):
        return f"Erro ao buscar conversas: {convs.get('error')}"

    if not convs:
        return "Nenhuma conversa ativa"

    lines = []
    for c in convs:
        cid = c.get("id") or c.get("conversation_id") or "unknown"
        started = c.get("started_at") or c.get("started") or ""
        participants = ",".join(c.get("participants") or [])
        phase = c.get("phase") or ""
        msg_count = c.get("message_count") or (
            len(c.get("messages", [])) if isinstance(c, dict) else ""
        )
        preview = ""
        if isinstance(c, dict):
            preview = c.get("preview") or ""
            if not preview and c.get("messages"):
                last = c.get("messages")[-1]
                if isinstance(last, dict):
                    preview = last.get("content") or last.get("message") or ""

        header = f"[{cid}] {participants} | phase={phase} | started={started} | messages={msg_count}"
        lines.append(header)
        if preview:
            lines.append(f"  » {preview}")
        lines.append("")

    return "\n".join(lines)


st.title("Conversations (simple)")
st.markdown(
    "Simple view: a read-only textbox with conversation summaries retrieved from the interceptor API."
)

convs = fetch_conversations(INTERCEPTOR_API)
text = format_conversations(convs)

st.text_area("Conversations", value=text, height=700)

if st.button("Refresh"):
    st.experimental_rerun()
