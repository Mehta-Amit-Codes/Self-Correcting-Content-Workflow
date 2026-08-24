# 🤖 Self-Correcting Content Workflow

A **cyclic LangGraph workflow** built with Python, Groq, and Streamlit that generates content, critiques its own output against a quality rubric, and automatically loops back to revise it — until the content passes or a retry limit is reached. A human-in-the-loop approval step gates the final output.

```
Generator → Critic → Conditional Router → Generator (loop)
                            │
                            ▼
                     Human Approval → END
```

## 📌 Concept

LangGraph models an AI app as a **graph of nodes connected by edges**, with a typed state shared between them. Unlike a simple linear chain, it supports **loops and conditional branches** — so the app can critique its own output and go back and fix it, like a flowchart the LLM walks through while remembering everything it has done so far.

This project generates a piece of content (blog section, email, code snippet, etc.), has a **critic** node score it against a rubric, and loops back to revise it until it passes or hits a retry limit — then hands off to a human for final approval.

## ✨ Features

- **Generator node** — drafts content from scratch, or revises the previous draft using the critic's feedback on retries.
- **Critic node** — scores the draft 0–10 against clarity, accuracy, relevance, tone, structure, and grammar, returning a strict `SCORE / STATUS / FEEDBACK` result. A score of **8+** is a `PASS`.
- **Conditional routing** — `FAIL` + attempts remaining loops back to the generator; `PASS` or retry limit reached moves to human approval.
- **Human-in-the-loop interrupt** — the graph is compiled with `interrupt_before=["human_approval"]`, so execution genuinely pauses at that node until the Streamlit UI supplies a real decision and resumes the graph.
- **Checkpointing** — an in-memory `MemorySaver` checkpointer tracks state per session (`thread_id`), enabling the interrupt/resume pattern.
- **Configurable model** — the Groq model is read from `GROQ_MODEL` (env var) instead of being hard-coded.
- **Execution history log** — every generator/critic/approval transition is recorded and shown in the UI, so the self-correction loop is visible.
- **Streamlit UI** — sidebar configuration, live metrics, draft + critique display, approval controls, and a "Start New Session" reset.

## 🧱 Project Structure

```
self_correcting_content_workflow/
│
├── app.py             # Streamlit UI
├── graph.py            # LangGraph StateGraph: nodes, edges, routing, checkpointing
├── nodes.py            # generator_node, critic_node, human_approval_node
├── prompts.py          # System prompts + rubric for Generator and Critic
├── state.py            # Typed ContentState shared across all nodes
├── requirements.txt    # Python dependencies
└── .env.example        # Required environment variables
```

| File | Responsibility |
|---|---|
| `state.py` | Defines `ContentState` — a `TypedDict` holding topic, content type, tone, draft, critique, score, pass/fail, attempt counter, approval flag, and history log. |
| `prompts.py` | `GENERATOR_SYSTEM_PROMPT` and `CRITIC_SYSTEM_PROMPT`, including the six-point critic rubric and the required `SCORE:` / `STATUS:` / `FEEDBACK:` output format. |
| `nodes.py` | The three node functions that call the LLM (via `ChatGroq`) and update state: `generator_node`, `critic_node`, `human_approval_node`. |
| `graph.py` | Builds and compiles the `StateGraph`: wires up nodes, defines `route_after_critic` and `route_after_human`, and sets up the `MemorySaver` checkpointer + human-approval interrupt. |
| `app.py` | Streamlit front end: collects input, runs/resumes the graph, and renders drafts, critiques, metrics, history, and approval controls. |

## ⚙️ How the Graph Works

```
                 ┌─────────────┐
                 │    START    │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │  generator  │◄────────────┐
                 └──────┬──────┘             │
                        ▼                    │
                 ┌─────────────┐             │
                 │   critic    │             │
                 └──────┬──────┘             │
                        ▼                    │
              route_after_critic             │
              │               │              │
            FAIL            PASS /           │
        (attempts left)   limit reached      │
              │               │              │
              └───────────────┼──────────────┘
                               ▼
                     ┌──────────────────┐
                     │  human_approval  │  ◄── graph pauses here (interrupt)
                     └────────┬─────────┘
                               ▼
                     route_after_human
                     │               │
                  approved       revision
                     │               │
                     ▼               └────► back to generator
                    END
```

1. **`generator_node`** — builds a prompt from the topic, content type, and tone. If a previous draft and critique exist, it includes both and instructs the model to fix every issue raised.
2. **`critic_node`** — sends the draft to the LLM with the critic rubric, then uses regex to extract `SCORE` and `STATUS` from the response.
3. **`route_after_critic`** — `PASS` → `human_approval`; `FAIL` with attempts remaining → `generator`; `FAIL` at the retry limit → `human_approval` anyway.
4. **`human_approval_node`** — a no-op node that only exists as the interrupt target; the real decision comes from the UI.
5. **`route_after_human`** — `approved` → `END`; otherwise → back to `generator` with the reviewer's note as new "critic" feedback.

## 🛠️ Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and set your [Groq](https://console.groq.com/keys) API key:

```
GROQ_API_KEY=your_groq_api_key_here

# Optional — defaults to llama-3.3-70b-versatile
GROQ_MODEL=llama-3.3-70b-versatile
```

### 3. Run the app

```bash
streamlit run app.py
```

Streamlit will print a local URL (typically `http://localhost:8501`) — open it in your browser.

## 🖥️ Usage

1. In the sidebar, choose a **content type** (Blog Section, Email, Code Snippet, Product Description, Technical Explanation, LinkedIn Post), a **tone**, and the **maximum number of attempts** (1–5).
2. Enter a topic describing what you'd like generated.
3. Click **🚀 Generate & Self-Correct**. The graph runs `generator → critic` automatically, looping until the content passes or the retry limit is hit, then pauses at the human-approval interrupt.
4. Review the **draft**, **critic evaluation**, **metrics** (attempts / score / status), and the **execution history**.
5. Choose **✅ Approve** to finalize the content, or **🔄 Request Revision** to send it back through the generator with your feedback.
6. Use **🔄 Start New Session** in the sidebar to reset the thread and start over.

## 💾 Checkpointing & State

Each browser session gets a unique `thread_id` (via `uuid.uuid4()`), which is passed to the graph on every `invoke`/`update_state` call:

```python
config = {"configurable": {"thread_id": st.session_state.thread_id}}
```

The `MemorySaver` checkpointer uses this thread id to persist state between the initial run and the resumed run after human approval. This is **in-memory only** — it's ideal for local development and demos, but state will not survive an app/process restart. Swap in a persistent checkpointer (e.g. Postgres) for production use.

## 📦 Dependencies

- [`langgraph`](https://github.com/langchain-ai/langgraph) — cyclic graph orchestration, conditional routing, checkpointing, interrupts
- [`langchain`](https://github.com/langchain-ai/langchain) / `langchain-core`
- [`langchain-groq`](https://github.com/langchain-ai/langchain-groq) — Groq LLM integration
- [`streamlit`](https://streamlit.io/) — web UI
- `python-dotenv` — loads `GROQ_API_KEY` / `GROQ_MODEL` from `.env`
- `typing-extensions`

## 🧠 Concepts Demonstrated

- **Graph vs. chain** — why cycles and conditional branching matter for self-correcting agents, not just linear pipelines.
- **Shared, typed state** — a single `TypedDict` schema (`ContentState`) coordinating every node.
- **Conditional routing** — `route_after_critic` and `route_after_human` decide the next node based on the current state.
- **Checkpointing & interrupts** — `MemorySaver` + `interrupt_before=["human_approval"]` pause and resume execution around a real human decision.
- **Human-in-the-loop** — final content only ships after explicit approval.

## 🔮 Possible Extensions

- Replace `MemorySaver` with a persistent (e.g. Postgres) checkpointer so runs survive restarts.
- Use separate models for the generator vs. critic roles.
- Replace regex-based critic parsing with structured output (e.g. a Pydantic schema).
- Let the human reviewer type specific revision instructions instead of a generic "please revise" note.
- Add tracing/observability (e.g. LangSmith) to monitor prompts, latency, and token usage across the loop.