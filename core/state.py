from typing import TypedDict, List, Annotated
import operator

class ShiftLeftState(TypedDict):
    issue_text: str
    repo_map: dict
    current_code: str
    test_results: dict
    error_logs: str
    agent_messages: Annotated[List[str], operator.add] 
    
    tests_passed: bool
    requires_human: bool