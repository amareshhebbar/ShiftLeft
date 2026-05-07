import os
import re
from dotenv import load_dotenv

from core.state import ShiftLeftState
from utils.config import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

gemini_model = os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite-preview"

def extract_code(text: str) -> str:
    """Helper function to strip markdown formatting and return pure Python code."""
    pattern = r"```(?:python)?\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def coder_node(state: ShiftLeftState):
    print("\033[94m[Coder Agent] Engaging main engine...\033[0m")
    
    llm = get_llm(model_name=gemini_model, temperature=0)
    error_logs = state.get("error_logs", "")
    is_retry = bool(error_logs)
    
    if is_retry:
        print("\033[93m[Coder Agent] Processing Sandbox failure logs. Rewriting code...\033[0m")
        action_message = "Attempting to fix previous test failure."
    else:
        print("\033[94m[Coder Agent] Drafting initial fix and unit tests...\033[0m")
        action_message = "Drafted initial code fix."

    system_prompt = """
    You are the Lead Developer Agent for an autonomous bug-fixing system.
    Your job is to read a GitHub issue, understand the codebase architecture, and write the Python code to fix the bug.
    
    CRITICAL CONSTRAINTS:
    1. Output ONLY valid, executable Python code. 
    2. Do NOT include explanations, greetings, or pleasantries.
    3. Include both the fixed functions AND a simple unit test (using pytest or standard assert) at the bottom of the script to verify the fix.
    """
    
    if is_retry:
        system_prompt += f"""
        WARNING: Your previous code failed the Sandbox Test. 
        Here is the error traceback:
        {error_logs}
        
        Analyze the error and rewrite the code to fix it.
        """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Issue Details: {issue_text}\n\nRepository Architecture: {repo_map}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    raw_response = chain.invoke({
        "issue_text": state["issue_text"],
        "repo_map": str(state["repo_map"])
    })
    executable_code = extract_code(raw_response)
    
    print("\033[94m[Coder Agent] Code generation complete.\033[0m")
    return {
        "current_code": executable_code,
        "agent_messages": [action_message]
    }