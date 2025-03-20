import os
os.environ["GROQ_API_KEY"] = "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"
from langchain_groq import ChatGroq
llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0
)