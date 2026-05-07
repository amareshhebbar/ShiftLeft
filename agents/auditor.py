import os
from dotenv import load_dotenv

from core.state import ShiftLeftState
from utils.config import get_llm
from tools.sandbox_tools import run_code_in_sandbox
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
gemini_model = os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite-preview"

def sandbox_node(state: ShiftLeftState):
    print("\033[93m[Sandbox Auditor] Executing code in isolated environment...\033[0m")
    
    current_code = state.get("current_code", "")
    if not current_code:
        print("\033[91m[Sandbox Auditor] No code provided to test.\033[0m")
        return {"tests_passed": False, "error_logs": "No code generated."}
    result = run_code_in_sandbox(current_code)
    
    if result["passed"]:
        print("\033[92m[Sandbox Auditor] Tests passed! Code is functional.\033[0m")
        return {
            "tests_passed": True,
            "error_logs": "",
            "agent_messages": ["Sandbox testing passed."]
        }
    else:
        print("\033[91m[Sandbox Auditor] Tests failed! Analyzing traceback...\033[0m")
        
        llm = get_llm(model_name=gemini_model, temperature=0)
        
        system_prompt = """
        You are the Sandbox Auditor.
        The Coder Agent just wrote a script, but it crashed during execution.
        Read the execution logs/traceback and summarize EXACTLY why it failed in 1-2 sentences.
        Do not provide the code fix. Just explain the error clearly so the Coder knows what to fix.
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Code Executed:\n{code}\n\nExecution Logs:\n{logs}")
        ])
        
        chain = prompt | llm | StrOutputParser()
        
        feedback = chain.invoke({
            "code": current_code,
            "logs": result["logs"]
        })
        
        message = f"Sandbox failed. Feedback to Coder: {feedback}"
        print(f"\033[93m[Sandbox Auditor] {message}\033[0m")
        combined_logs = f"RAW TRACEBACK:\n{result['logs']}\n\nAUDITOR NOTES:\n{feedback}"
        
        return {
            "tests_passed": False,
            "error_logs": combined_logs,
            "agent_messages": [message]
        }