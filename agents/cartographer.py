import os
import json
from dotenv import load_dotenv

from core.state import ShiftLeftState
from utils.config import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools.ast_tools import generate_function_map

load_dotenv()

# The Cartographer needs high context to read architecture, so we prefer the Pro model here
gemini_model = os.getenv("GEMINI_MODEL") or "gemini-1.5-pro"

def cartographer_node(state: ShiftLeftState):
    print("\033[96m[Cartographer Agent] Scanning directories and mapping dependencies...\033[0m")
    
    # 1. Run the Tool (Hands)
    # For the hackathon, we scan the current ShiftLeft directory itself as the "Mock Repo"
    raw_map = generate_function_map(".") 
    
    # 2. Get the LLM (Brain)
    llm = get_llm(model_name=gemini_model, temperature=0)
    
    # 3. Define the Prompt
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
    
    # 4. Call Gemini
    architecture_summary = chain.invoke({"raw_map": json.dumps(raw_map)})
    
    message = f"Mapping complete. Found {len(raw_map)} relevant Python files."
    print(f"\033[96m[Cartographer Agent] {message}\033[0m")
    # Uncomment the line below if you want to see Gemini's summary in your terminal!
    # print(f"\033[90m{architecture_summary}\033[0m") 
    
    # 5. Update the LangGraph State
    return {
        "repo_map": raw_map, 
        "agent_messages": [message, f"Architecture Summary: {architecture_summary}"]
    }