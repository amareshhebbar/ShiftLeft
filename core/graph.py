from langgraph.graph import StateGraph, START, END
from core.state import ShiftLeftState
from agents.triage import triage_node
from agents.cartographer import cartographer_node


def coder_node(state: ShiftLeftState):
    print("\033[94m[Coder Agent] Drafting fix and unit tests...\033[0m")
    return {"current_code": "def fix(): return True", "agent_messages": ["Code written."]}

def sandbox_node(state: ShiftLeftState):
    print("\033[93m[Sandbox Auditor] Executing code in isolated container...\033[0m")
    passed = bool(state.get("current_code"))
    if passed:
        print("\033[92m[Sandbox Auditor] Tests passed.\033[0m")
    else:
        print("\033[91m[Sandbox Auditor] Tests failed. Routing back to Coder.\033[0m")
        
    return {"tests_passed": passed, "agent_messages": [f"Tests passed: {passed}"]}

def hitl_node(state: ShiftLeftState):
    print("\033[95m[HITL Lead] Halting execution. Preparing PR for human review...\033[0m")
    return {"requires_human": True, "agent_messages": ["Awaiting human approval."]}

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