import os
os.environ["GROQ_API_KEY"] = ""
from langchain_groq import ChatGroq
llm = ChatGroq(
    model_name="llama-3.3-70b-versatil",
    temperature=0
)