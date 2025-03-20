import os
os.environ["GROQ_API_KEY"] = "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"
from langchain_groq import ChatGroq
llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0
)