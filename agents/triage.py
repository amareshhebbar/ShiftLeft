import os
from dotenv import load_dotenv

from core.state import ShiftLeftState
from utils.config import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser  # 1. NEW IMPORT

load_dotenv()

gemini_model = os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite-preview"

def triage_node(state: ShiftLeftState):
    print("\033[92m[Triage Agent] Categorizing issue...\033[0m")
    
    llm = get_llm(model_name=gemini_model, temperature=0)
    
    # 2. Define the Prompt
    system_prompt = """
    You are the Triage Agent for an open-source repository.
    Read the following issue and categorize it. 
    Respond ONLY with one of the following words: BUG, FEATURE, DOCS, or OTHER.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Issue Text: {issue_text}")
    ])
    
    # 3. Add the StrOutputParser to the chain
    chain = prompt | llm | StrOutputParser()
    
    # 4. Call Gemini (response is now guaranteed to be a string!)
    response = chain.invoke({"issue_text": state["issue_text"]})
    category = response.strip().upper()
    
    message = f"Triage complete: Identified as {category}."
    print(f"\033[92m[Triage Agent] {message}\033[0m")
    
    # Update the LangGraph State
    return {"agent_messages": [message]}