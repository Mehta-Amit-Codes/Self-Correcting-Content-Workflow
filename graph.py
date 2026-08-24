from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from nodes import critic_node, generator_node, human_approval_node
from state import ContentState


def route_after_critic(state: ContentState) -> str:
    """
    PASS                          -> human approval
    FAIL + attempts remaining     -> back to generator (self-correction loop)
    FAIL + retry limit reached    -> human approval anyway
    """
    if state["passed"]:
        return "human_approval"

    if state["attempt"] < state["max_attempts"]:
        return "generator"

    return "human_approval"


def route_after_human(state: ContentState) -> str:
    """
    approved   -> end the workflow
    otherwise  -> loop back to the generator with the reviewer's note
    """
    if state.get("approved"):
        return "end"

    return "generator"


def build_graph():
    workflow = StateGraph(ContentState)

    # --- Nodes ---
    workflow.add_node("generator", generator_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("human_approval", human_approval_node)

    # --- Edges ---
    workflow.add_edge(START, "generator")
    workflow.add_edge("generator", "critic")

    workflow.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "generator": "generator",
            "human_approval": "human_approval",
        },
    )

    workflow.add_conditional_edges(
        "human_approval",
        route_after_human,
        {
            "generator": "generator",
            "end": END,
        },
    )

    # --- Checkpointing (stretch goal: resumable runs) ---
    # In-memory here for simplicity/local dev. Swap for a persistent
    # checkpointer (e.g. Postgres) to survive process restarts.
    memory = MemorySaver()

    # --- Human-in-the-loop interrupt (stretch goal) ---
    # Execution pauses right before human_approval runs, so the
    # Streamlit UI can collect a real approval decision before resuming.
    return workflow.compile(
        checkpointer=memory,
        interrupt_before=["human_approval"],
    )