# smartMail-Agent

LangGraph + LangChain email assistant: describe the email in natural language, review/revise the draft, and send it over SMTP.

## Setup

```bash
uv sync
cp .env.example .env   # fill in OPENAI_* and SMTP_* values
```

## Run

UI (recommended):

```bash
uv run streamlit run app.py
```

CLI:

```bash
uv run agent.py
```

The app extracts recipient/reason from your request, drafts a subject and body, lets you approve or request revisions (max 2 feedback rounds), then sends via SMTP. Type `q`/`quit`/`exit` to exit the CLI.

## Layout

- `app.py` — Streamlit UI (secrets form writes `.env`)
- `email_graph.py` — graph definition, state models, nodes
- `agent.py` — CLI REPL
- `tools.py` — SMTP `send_email`
