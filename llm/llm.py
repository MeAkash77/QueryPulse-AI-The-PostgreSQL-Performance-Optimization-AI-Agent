import os
from dotenv import load_dotenv

from langchain_groq import ChatGroq as Groq
from langchain_ollama import ChatOllama as Ollama

# Load .env
load_dotenv()

# Get provider safely
provider = os.getenv("LLM_PROVIDER", "groq").lower()

# Helper function
def get_env(key, default=None):
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"❌ Missing environment variable: {key}")
    return value

# -------------------------------
# GROQ CONFIG
# -------------------------------
if provider == "groq":
    groq_api_key = get_env("GROQ_API_KEY")
    model_name = os.getenv("GROQ_MODEL", "llama3-8b-8192")
    analyze_model = os.getenv("ANALYZING_MODEL", model_name)

    llm = Groq(
        model_name=model_name,
        groq_api_key=groq_api_key,
        temperature=0.1
    )

    analyze_llm = Groq(
        model_name=analyze_model,
        groq_api_key=groq_api_key,
        temperature=0.1
    )

    ollama_llm = None


# -------------------------------
# OLLAMA CONFIG
# -------------------------------
elif provider == "ollama":
    ollama_model = get_env("OLLAMA_MODEL", "llama3")

    llm = Ollama(
        model=ollama_model,
        temperature=0.1
    )

    analyze_llm = llm
    ollama_llm = llm


# -------------------------------
# ERROR HANDLING
# -------------------------------
else:
    raise ValueError("❌ Invalid LLM_PROVIDER. Use 'groq' or 'ollama'")
