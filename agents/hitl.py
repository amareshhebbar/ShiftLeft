from core.state import ShiftLeftState

def hitl_node(state: ShiftLeftState):
    print("\033[95m[HITL Lead] Halting execution. Preparing PR for human review...\033[0m")
    
    code = state.get("current_code", "No code generated.")
    logs = state.get("error_logs", "No errors recorded.")
    
    summary = f"""
### 🛠️ ShiftLeft Autonomous Fix Ready

**Issue:** {state.get('issue_text')}

**Status:** ✅ Tests Passed in Sandbox
    
**Proposed Code Fix:**
```python
{code}
Sandbox Execution Logs:

Plaintext
{logs}
"""

    return {
        "requires_human": True, 
        "agent_messages": ["Awaiting human approval."],
        "error_logs": summary
    }