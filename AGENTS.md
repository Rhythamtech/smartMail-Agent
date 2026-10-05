# AGENTS.md

SmartMail agent: a LangGraph + LangChain (OpenAI) CLI that drafts, reviews, and sends emails over SMTP.

## Layout & entrypoints
- `app.py` — Streamlit UI (run `uv run streamlit run app.py`): sidebar form writes secrets to `.env` + `os.environ`, main pane drafts/reviews/sends via the graph. Prefer this over the CLI for interactive use.
- `email_graph.py` — graph definition (`build_graph()`), state models, nodes. Importable; no side-effect loop. LLM is constructed per node call from current env, so new secrets take effect without restarting the app.
- `agent.py` — thin CLI REPL wrapping `email_graph.build_graph()` under `if __name__ == "__main__"`.
- `tools.py` — safe to import.
- `main.py` and `README.md` are empty placeholders; `uv.lock`-managed Python 3.11 project (`pyproject.toml`, `.python-version`).

## Commands
- Install/sync deps: `uv sync`
- Run the CLI agent: `uv run agent.py` (REPL; review loop asks yes/no or free-text feedback, cancel after >2 feedback rounds)
- Run the UI: `uv run streamlit run app.py`
- No test suite, linter, typechecker, CI, or pre-commit hooks are configured — there is nothing to run beyond `uv sync` and executing the script.

## Environment
- `.env` is required (`python-dotenv` loads it). `.env.example` lists all keys including `SMTP_*`.
- Model comes from `OPENAI_MODEL` env var (default `gpt-5.6-luna`); `email_graph._llm()` reads it at call time.

## Gotchas
- Feedback router cancels after `feedback_count > 2`; `review_node` increments only on non-"yes" input. Approval must be the exact string `yes` to send.
- The graph uses `interrupt()` + `InMemorySaver` with a `thread_id`; state is checkpointed per thread within one process only.
- `EmailState`/`UserDetails`/`DraftMail` are Pydantic BaseModels used directly as graph state — `graph.invoke` is called with a plain dict, relying on langgraph coercion.
- `with_structured_output(...)` is NOT reliably honored by the configured endpoint: the model often returns JSON keys mirroring the prompt wording instead of schema keys. Prompts must spell out exact JSON keys, and pydantic fields must NOT have defaults (`""`), else missing keys silently become empty strings (this was the cause of empty body/recipient). `retriever_node` raises if reason/email are missing.
