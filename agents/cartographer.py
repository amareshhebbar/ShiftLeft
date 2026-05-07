import os
import json
from dotenv import load_dotenv

from core.state import ShiftLeftState
from utils.config import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools.ast_tools import generate_function_map

load_dotenv()

gemini_model = os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite-preview"

def cartographer_node(state: ShiftLeftState):
    print("\033[96m[Cartographer Agent] Scanning directories and mapping dependencies...\033[0m")
    
    raw_map = generate_function_map(".") 
    llm = get_llm(model_name=gemini_model, temperature=0)
    system_prompt = """
    You are the Codebase Cartographer.
    Analyze the following raw AST (Abstract Syntax Tree) map of a Python repository.
    Summarize the core architecture in 2-3 sentences. What are the main components and how do they relate?
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Raw AST Map: {raw_map}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    architecture_summary = chain.invoke({"raw_map": json.dumps(raw_map)})
    
    message = f"Mapping complete. Found {len(raw_map)} relevant Python files."
    print(f"\033[96m[Cartographer Agent] {message}\033[0m")
    # Uncomment the line below if you want to see Gemini's summary in your terminal!
    # print(f"\033[90m{architecture_summary}\033[0m") 

    return {
        "repo_map": raw_map, 
        "agent_messages": [message, f"Architecture Summary: {architecture_summary}"]
    }