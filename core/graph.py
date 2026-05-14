"""
LangGraph state machine wiring.

Graph topology:
  START → cartographer → triage → coder → auditor
                                     ↑         │
                                     └─────────┘ (self-correction, max 3x)
                                               │
                                             hitl → END
"""

from langgraph.graph import StateGraph, START, END

from core.state import ShiftLeftState
from agents.cartographer import cartographer_node
from agents.triage       import triage_node
from agents.coder        import coder_node
from agents.auditor      import sandbox_node
from agents.hitl         import hitl_node
from agents.researcher   import researcher_node   # optional; safe to remove


def route_after_audit(state: ShiftLeftState) -> str:
    """
    Conditional edge out of the auditor node.
    - If tests passed (or max iterations hit) → hitl
    - Otherwise → coder  (self-correction loop)
    """
    if state.get("tests_passed"):
        return "hitl"
    return "coder"


# ── Build the graph ────────────────────────────────────────────────────────

workflow = StateGraph(ShiftLeftState)

workflow.add_node("cartographer", cartographer_node)
workflow.add_node("triage",       triage_node)
workflow.add_node("coder",        coder_node)
workflow.add_node("auditor",      sandbox_node)
workflow.add_node("hitl",         hitl_node)
# workflow.add_node("researcher", researcher_node)  # uncomment to enable

workflow.add_edge(START,          "cartographer")
workflow.add_edge("cartographer", "triage")
# workflow.add_edge("triage",     "researcher")     # uncomment to enable
workflow.add_edge("triage",       "coder")
workflow.add_edge("coder",        "auditor")

workflow.add_conditional_edges(
    "auditor",
    route_after_audit,
    {"hitl": "hitl", "coder": "coder"},
)

workflow.add_edge("hitl", END)

shiftleft_app = workflow.compile()