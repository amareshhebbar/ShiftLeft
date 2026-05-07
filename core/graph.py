from langgraph.graph import StateGraph, START, END
from core.state import ShiftLeftState
from agents.triage import triage_node
from agents.cartographer import cartographer_node
from agents.coder import coder_node
from agents.auditor import sandbox_node
from agents.hitl import hitl_node

def route_sandbox_results(state: ShiftLeftState):
    """The Self-Correction Loop"""
    if state.get("tests_passed"):
        return "hitl"
    return "coder"

workflow = StateGraph(ShiftLeftState)

workflow.add_node("triage", triage_node)
workflow.add_node("cartographer", cartographer_node)
workflow.add_node("coder", coder_node)
workflow.add_node("sandbox", sandbox_node)
workflow.add_node("hitl", hitl_node)

workflow.add_edge(START, "triage")
workflow.add_edge("triage", "cartographer")
workflow.add_edge("cartographer", "coder")
workflow.add_edge("coder", "sandbox")

workflow.add_conditional_edges(
    "sandbox", 
    route_sandbox_results, 
    {"hitl": "hitl", "coder": "coder"}
)

workflow.add_edge("hitl", END)

shiftleft_app = workflow.compile()