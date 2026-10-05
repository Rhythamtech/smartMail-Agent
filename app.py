import os
from pathlib import Path
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from email_graph import build_graph

load_dotenv()

ENV_PATH = Path(__file__).parent / ".env"

SECRET_KEYS = [
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
]


def save_env(values: dict[str, str]) -> None:
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    seen = set()
    out = []
    for line in lines:
        if "=" in line and line.split("=", 1)[0].strip() in values:
            key = line.split("=", 1)[0].strip()
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, val in values.items():
        if key not in seen and val:
            out.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(out) + "\n")
    for key, val in values.items():
        if val:
            os.environ[key] = val


def missing_secrets() -> list[str]:
    required = ["OPENAI_API_KEY", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD"]
    return [k for k in required if not os.environ.get(k)]


st.set_page_config(page_title="SmartMail Agent", page_icon="✉️")
st.title("✉️ SmartMail Agent")

with st.sidebar:
    st.header("Secrets")
    with st.form("secrets"):
        values = {}
        for key in SECRET_KEYS:
            values[key] = st.text_input(
                key,
                value=os.environ.get(key, ""),
                type="password" if "KEY" in key or "PASSWORD" in key or "SECRET" in key else "default",
            )
        if st.form_submit_button("Save secrets"):
            save_env(values)
            st.session_state.pop("graph", None)
            st.success("Saved to .env")
            st.rerun()
    missing = missing_secrets()
    if missing:
        st.warning(f"Missing: {', '.join(missing)}")
    else:
        st.success("All required secrets set")

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
if "config" not in st.session_state:
    st.session_state.config = None
if "res" not in st.session_state:
    st.session_state.res = None
if "done" not in st.session_state:
    st.session_state.done = False

graph = st.session_state.graph

missing = missing_secrets()
if missing:
    st.info(f"Set these secrets in the sidebar first: {', '.join(missing)}")

query = st.text_area("What email do you want to send?", placeholder="Email Alice at alice@example.com asking to reschedule our meeting to Friday")
if st.button("Draft email", disabled=bool(missing)) and query.strip():
    st.session_state.config = {"configurable": {"thread_id": str(uuid4())}}
    st.session_state.done = False
    with st.spinner("Drafting..."):
        st.session_state.res = graph.invoke({"question": query}, config=st.session_state.config)

config = st.session_state.config
res = st.session_state.res

if config and res is not None:
    state = graph.get_state(config)
    if state.next:
        st.subheader("Review draft")
        st.write(f"**To:** {res.get('recipient_name', '')} <{res.get('recipient_email', '')}>")
        st.write(f"**Subject:** {res.get('subject', '')}")
        st.text_area("Body", res.get("body", ""), height=200, disabled=True)
        col1, col2 = st.columns(2)
        if col1.button("✅ Approve & send"):
            with st.spinner("Sending..."):
                st.session_state.res = graph.invoke(Command(resume="yes"), config=config)
            st.rerun()
        feedback = col2.text_input("Feedback for rewrite")
        if col2.button("✏️ Rewrite with feedback") and feedback.strip():
            with st.spinner("Rewriting..."):
                st.session_state.res = graph.invoke(Command(resume=feedback), config=config)
            st.rerun()
    else:
        st.success(res.get("response", "Done"))
        if st.button("Send another"):
            st.session_state.res = None
            st.session_state.config = None
            st.rerun()
