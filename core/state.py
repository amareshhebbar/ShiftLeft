from __future__ import annotations

from typing import Any, Dict, List, TypedDict

class PatchFile(TypedDict, total=False):
    file_path:        str
    original_content: str
    patched_content:  str
    diff:             str


class TestResult(TypedDict, total=False):
    passed: bool
    output: str   
    error:  str  


# ── Main pipeline state ────────────────────────────────────────────────────────

class ShiftLeftState(TypedDict, total=False):
    run_id:         str  
    repo_url:       str   
    trigger_source: str   

    gitlab_project_id: str           
    open_issues:       List[Dict[str, Any]]  

    branch_name:    str         
    file_map:       Dict[str, Any]

    yaml_map:       Dict[str, str]
    repo_local_path: str

    issue_summary: str         
    target_files:  List[str]   
    severity:      str         

    patches: List[Dict[str, Any]]

    iteration: int 

    test_results: str   
    tests_passed: bool 

    pr_url:        str            
    pr_number:     int           
    diff_hunks:    List[Dict[str, Any]] 
    changed_files: List[str]     