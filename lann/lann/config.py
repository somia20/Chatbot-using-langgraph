import os
os.environ["GROQ_API_KEY"] = "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"
from langchain_groq import ChatGroq
llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0
)