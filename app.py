import uuid

import streamlit as st

from graph import build_graph

# --------------------------------------------------
# Page Configuration
# --------------------------------------------------

st.set_page_config(
    page_title="Self-Correcting Content Workflow",
    page_icon="🤖",
    layout="wide",
)

# --------------------------------------------------
# Initialize Graph + Session State
# --------------------------------------------------

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()

if "thread_id" not in st.session_state:
    # Each new session gets its own checkpointer thread, so the graph
    # can be resumed (e.g. after a human-approval interrupt) using
    # this id.
    st.session_state.thread_id = str(uuid.uuid4())

if "workflow_state" not in st.session_state:
    st.session_state.workflow_state = None

# --------------------------------------------------
# Header
# --------------------------------------------------

st.title("🤖 Self-Correcting Content Workflow")

st.markdown(
    """
This app demonstrates a **cyclic LangGraph workflow**: an LLM generates
content, a second LLM critiques it against a rubric, and the workflow
loops back to revise the draft until it passes or hits a retry limit.

**Generator → Critic → Conditional Router → Generator (loop) → Human Approval**
"""
)

# --------------------------------------------------
# Sidebar — Workflow Configuration
# --------------------------------------------------

with st.sidebar:
    st.header("⚙️ Workflow Configuration")

    content_type = st.selectbox(
        "Content Type",
        [
            "Blog Section",
            "Email",
            "Code Snippet",
            "Product Description",
            "Technical Explanation",
            "LinkedIn Post",
        ],
    )

    tone = st.selectbox(
        "Tone",
        ["Professional", "Technical", "Friendly", "Concise", "Persuasive"],
    )

    max_attempts = st.slider(
        "Maximum Attempts",
        min_value=1,
        max_value=5,
        value=3,
    )

    st.divider()

    st.info("The critic passes content when its score is 8/10 or higher.")

    if st.button("🔄 Start New Session", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.workflow_state = None
        st.rerun()

# --------------------------------------------------
# Main Input
# --------------------------------------------------

topic = st.text_area(
    "What would you like the AI to create?",
    placeholder=(
        "Example: Explain how event-driven architecture "
        "improves scalability in backend systems."
    ),
    height=120,
)

config = {"configurable": {"thread_id": st.session_state.thread_id}}

# --------------------------------------------------
# Run Workflow
# --------------------------------------------------

if st.button("🚀 Generate & Self-Correct", type="primary", use_container_width=True):
    if not topic.strip():
        st.warning("Please enter a topic.")
    else:
        initial_state = {
            "topic": topic,
            "content_type": content_type,
            "tone": tone,
            "draft": "",
            "critique": "",
            "score": 0,
            "passed": False,
            "attempt": 0,
            "max_attempts": max_attempts,
            "approved": False,
            "history": [],
        }

        with st.spinner("AI is generating and self-correcting..."):
            # The graph runs generator -> critic -> (loop) automatically,
            # then pauses at human_approval because of interrupt_before.
            result = st.session_state.graph.invoke(initial_state, config=config)

        st.session_state.workflow_state = result
        st.rerun()

# --------------------------------------------------
# Display Workflow State
# --------------------------------------------------

state = st.session_state.workflow_state

if state:
    st.divider()

    # ---- Metrics ----
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Attempts", state["attempt"])

    with col2:
        st.metric("Critic Score", f"{state['score']}/10")

    with col3:
        status = "✅ Passed" if state["passed"] else "❌ Needs Improvement"
        st.metric("Status", status)

    # ---- Draft ----
    st.subheader("📝 Current Draft")
    st.markdown(state["draft"])

    # ---- Critic Evaluation ----
    st.subheader("🔍 Critic Evaluation")
    st.code(state["critique"], language="text")

    # ---- Self-Correction History ----
    with st.expander("🔄 Workflow Execution History", expanded=True):
        for event in state["history"]:
            st.write(f"• {event}")

    # ---- Human-in-the-Loop Approval ----
    # The graph is paused right before human_approval, so this reflects
    # a real interrupt — clicking Approve/Revise resumes execution.
    if state["passed"] or state["attempt"] >= state["max_attempts"]:
        st.divider()
        st.subheader("👤 Human Approval Required")
        st.write(
            "The automated workflow has reached the approval checkpoint. "
            "Review the draft above and decide how to proceed."
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("✅ Approve", use_container_width=True):
                # Update state, then resume the interrupted graph.
                st.session_state.graph.update_state(config, {"approved": True})
                result = st.session_state.graph.invoke(None, config=config)
                st.session_state.workflow_state = result
                st.success("Content approved successfully!")
                st.rerun()

        with col2:
            if st.button("🔄 Request Revision", use_container_width=True):
                st.session_state.graph.update_state(
                    config,
                    {
                        "approved": False,
                        "critique": "Human reviewer requested another revision.",
                    },
                )
                result = st.session_state.graph.invoke(None, config=config)
                st.session_state.workflow_state = result
                st.rerun()

    # ---- Final Output ----
    if state.get("approved"):
        st.divider()
        st.subheader("🎉 Final Approved Content")
        st.success("Human approval received.")
        st.markdown(state["draft"])