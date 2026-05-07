import os
from dotenv import load_dotenv

try:
    from langchain_google_vertexai import ChatVertexAI
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

load_dotenv()

def get_llm(model_name="gemini-3.1-flash-lite-preview", temperature=0):
    """
    Dynamically loads the LLM. 
    Tries GCP/Vertex AI first. Falls back to Standard Gemini API.
    """
    gcp_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    gcp_project = os.getenv("GCP_PROJECT_ID")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if gcp_creds and gcp_project and VERTEX_AVAILABLE:
        try:
            print(f"🔌 [Config] Connecting to Enterprise Vertex AI ({model_name})...")
            return ChatVertexAI(
                model_name=model_name, 
                temperature=temperature, 
                project=gcp_project
            )
        except Exception as e:
            print(f"⚠️ [Config] Vertex AI failed ({e}). Falling back to standard API...")

    if gemini_key and GENAI_AVAILABLE:
        print(f"🔌 [Config] Connecting to Standard Gemini API ({model_name})...")
        return ChatGoogleGenerativeAI(
            model=model_name, 
            temperature=temperature, 
            google_api_key=gemini_key
        )

    raise ValueError(
        "No valid AI credentials found. "
        "Please set either GOOGLE_APPLICATION_CREDENTIALS/GCP_PROJECT_ID "
        "OR GEMINI_API_KEY in your .env file."
    )