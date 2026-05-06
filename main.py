from core.graph import shiftleft_app
from core.state import ShiftLeftState

def main():
    print("=== Initiating ShiftLeft Autonomous Workflow ===")
    
    initial_state: ShiftLeftState = {
        "issue_text": "Bug: Database connection drops under load.",
        "repo_map": {},
        "current_code": "",
        "test_results": {},
        "error_logs": "",
        "agent_messages": [],
        "tests_passed": False,
        "requires_human": False
    }

    for output in shiftleft_app.stream(initial_state):
        for node_name, node_state in output.items():
            pass 

    print("=== Workflow Complete ===")

if __name__ == "__main__":
    main()