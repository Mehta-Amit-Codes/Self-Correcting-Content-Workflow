from typing import List, TypedDict

class ContentState(TypedDict):
    # --- Request inputs ---
    topic: str
    content_type: str   # e.g. "Blog Section", "Email", "Code Snippet"
    tone: str            # e.g. "Professional", "Technical", "Friendly"

    # --- Generator output ---
    draft: str

    # --- Critic output ---
    critique: str        # raw critic response (SCORE / STATUS / FEEDBACK)
    score: float          # 0-10
    passed: bool          # True once score >= threshold

    # --- Retry / loop control ---
    attempt: int
    max_attempts: int

    # --- Human-in-the-loop ---
    approved: bool

    # --- Observability ---
    history: List[str]   # human-readable log of every node transition