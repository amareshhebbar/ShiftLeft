from langgraph.graph import StateGraph, START, END

from core.state      import ShiftLeftState
from agents.cartographer import cartographer
from agents.triage       import triage
from agents.coder        import coder
from agents.auditor      import auditor
from agents.hitl         import hitl

MAX_ITERATIONS = 3


def route_after_audit(state: ShiftLeftState) -> str:
    if state.get("tests_passed"):
        return "hitl"
    if (state.get("iteration") or 0) >= MAX_ITERATIONS:
        return "hitl"   
    return "coder"


workflow = StateGraph(ShiftLeftState)

workflow.add_node("cartographer", cartographer)
workflow.add_node("triage",       triage)
workflow.add_node("coder",        coder)
workflow.add_node("auditor",      auditor)
workflow.add_node("hitl",         hitl)

workflow.add_edge(START,          "cartographer")
workflow.add_edge("cartographer", "triage")
workflow.add_edge("triage",       "coder")
workflow.add_edge("coder",        "auditor")

workflow.add_conditional_edges(
    "auditor",
    route_after_audit,
    {"hitl": "hitl", "coder": "coder"},
)

workflow.add_edge("hitl", END)

shiftleft_app = workflow.compile()