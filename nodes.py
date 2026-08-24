import os
import re

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from prompts import CRITIC_SYSTEM_PROMPT, GENERATOR_SYSTEM_PROMPT
from state import ContentState

load_dotenv()

PASS_THRESHOLD = 8.0

# Model is configurable via .env so it's easy to swap without touching code.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=0.4,
    api_key=os.getenv("GROQ_API_KEY"),
)


def generator_node(state: ContentState) -> dict:
    """
    Creates the first draft, or revises the previous draft using the
    critic's feedback if this is a retry.
    """

    topic = state["topic"]
    content_type = state["content_type"]
    tone = state["tone"]

    previous_draft = state.get("draft", "")
    critique = state.get("critique", "")

    if previous_draft and critique:
        user_prompt = f"""
Topic:
{topic}

Content Type:
{content_type}

Tone:
{tone}

Previous Draft:
{previous_draft}

Critic Feedback:
{critique}

Rewrite the draft and address every issue raised by the critic.
"""
    else:
        user_prompt = f"""
Topic:
{topic}

Content Type:
{content_type}

Tone:
{tone}

Create the first draft.
"""

    response = llm.invoke(
        [
            ("system", GENERATOR_SYSTEM_PROMPT),
            ("human", user_prompt),
        ]
    )

    new_attempt = state.get("attempt", 0) + 1

    history = list(state.get("history", []))
    history.append(f"Attempt {new_attempt}: Generator created/revised the draft.")

    return {
        "draft": response.content,
        "attempt": new_attempt,
        "history": history,
    }


def critic_node(state: ContentState) -> dict:
    """
    Scores the current draft against the rubric and extracts a
    structured SCORE / STATUS / FEEDBACK result via regex.
    """

    draft = state["draft"]

    prompt = f"""
Evaluate this content:

-------------------------
CONTENT
-------------------------

{draft}

-------------------------
END CONTENT
-------------------------
"""

    response = llm.invoke(
        [
            ("system", CRITIC_SYSTEM_PROMPT),
            ("human", prompt),
        ]
    )

    result = response.content

    score_match = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)", result, re.IGNORECASE)
    status_match = re.search(r"STATUS:\s*(PASS|FAIL)", result, re.IGNORECASE)

    score = float(score_match.group(1)) if score_match else 0.0

    passed = (
        status_match.group(1).upper() == "PASS"
        if status_match
        else score >= PASS_THRESHOLD
    )

    history = list(state.get("history", []))
    history.append(
        f"Attempt {state['attempt']}: Critic scored {score}/10 - "
        f"{'PASS' if passed else 'FAIL'}."
    )

    return {
        "critique": result,
        "score": score,
        "passed": passed,
        "history": history,
    }


def human_approval_node(state: ContentState) -> dict:
    """
    Interrupt point. The graph is compiled with
    interrupt_before=["human_approval"], so execution pauses here
    until the Streamlit UI supplies an approval decision and resumes
    the graph.
    """

    history = list(state.get("history", []))
    history.append("Workflow reached human approval stage.")

    return {"history": history}