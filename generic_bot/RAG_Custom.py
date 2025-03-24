import os
from typing import Dict, Any, List
from flask import Flask, request, jsonify
from flask import Response
from langchain_chroma import Chroma
from langchain_community.embeddings import SentenceTransformerEmbeddings
from groq import Groq
from pydantic import BaseModel, Field
from manager import ManagerAgent
import json

app = Flask(__name__)

# Pydantic models
class Message(BaseModel):
    role: str
    content: str

class SessionState(BaseModel):
    action: str = Field(default="")
    plan: Dict[str, bool] = Field(default_factory=dict)
    output: str = Field(default="processing request")
    messages: List[Message] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "order": ["action", "plan", "output", "messages"]
        }
    }

class Variables():
    def __init__(self):
        # Global state dictionary
        state: Dict[str, Dict[str, Any]] = {}
        self.state_dict = state

        # Groq setup
        GROQ_API_KEY = ""
        self.groq_client = Groq(api_key=GROQ_API_KEY)


        # Initialize embeddings and Chroma
        self.embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        # self.vectorstore = Chroma(persist_directory="chroma_db", embedding_function=self.embedding_function) if os.path.exists("chroma_db") else None
        self.vectorstore = Chroma(persist_directory="chroma_db", embedding_function=self.embedding_function) if os.path.exists("chroma_db") else None

    # Initialize State
    def InitiallizeState(self, session_id):
        self.state_dict[session_id] = SessionState().model_dump()

    # Update state for different message types
    def UpdateState(self, session_id, response):
        self.state_dict[session_id]["messages"].append({
            "role": "assistant",
            "content": response
        })
        self.state_dict[session_id]["action"] = ""
        self.state_dict[session_id]["plan"] = {}
        self.state_dict[session_id]["output"] = "processing request..."

    def UpdateState_information(self, session_id, response):
        self.state_dict[session_id]["messages"].append({
            "role": "assistant",
            "content": response
        })
        self.state_dict[session_id]["action"] = ""
        self.state_dict[session_id]["plan"] = {}
        self.state_dict[session_id]["output"] = "processing request..."

    def UpdateState_creation(self, session_id, user_input, parsed_schema):
        self.state_dict[session_id]["messages"].append({
            "role": "user",
            "content": user_input
        })

        if "action" in parsed_schema:
            self.state_dict[session_id]["action"] = parsed_schema["action"]

        if "fields" in parsed_schema:
            self.state_dict[session_id]["plan"] = parsed_schema["fields"]

        self.state_dict[session_id]["output"] = "processing request..."

    def UpdateState_User(self, session_id, received_message):
        self.state_dict[session_id]["messages"].append({
            "role": "user",
            "content": received_message
        })

    def getstate(self,conversation_id):
        state_dict = self.state_dict
        print("Initial state dict:", state_dict)

        if not state_dict:
            return state_dict

        for id, data in state_dict.items():
            action = data.get('action')
            if not action:
                print("STATE DICT (No action):", state_dict)
                return state_dict
            else:
                print("STATE DICT BEFORE MANAGER:", state_dict)
                manager = ManagerAgent()
                print("manager is called from RAG")
                result = manager.process_state(state_dict,conversation_id)
                print("MANAGER RESULT:", result)
                return result if result else state_dict

class Agent_RAG(Variables):
    def __init__(self):
        super().__init__()
        self.state_dict: Dict[str, Dict[str, Any]] = {}

    async def retrieve(self, query: str) -> list:
        if self.vectorstore:
            results = self.vectorstore.similarity_search(query, k=5)
            return [result.page_content for result in results]
        return []

    async def extract_schema(self, contexts: list, user_input: str, session_id: str) -> dict:
        context_str = "\n".join(contexts)


        system_prompt = """You are an AI assistant specialized in extracting structured information from user inputs.
    Your task is to identify the main action and required fields from user requests.

    -Always return a JSON object with 'action' and 'fields' keys.
    -initially keep all the value of all fields as false.
    -Only set a field to true if it is explicitly mentioned in the user input otherwise set every field to false.
    -Extract all possible fields required for the action.
    - Only extract those fields which are required for the action."""

        user_prompt = f"""Extract the main action and fields from this request.
    - initially keep all the value of all fields as false.
    - Only set a field to true if it is explicitly mentioned in the user input otherwise set every field to false
    - Extract all possible fields required for the action.
    - Only extract those fields which are required for the action

    Context Information:
    {context_str}

    User Input:
    {user_input}

    Return the response in this exact JSON format:
    {{
        "action": "the_main_action",
        "fields": {{
            "field_name_1": true/false,
            "field_name_2": true/false
        }}
    }}"""

        try:
            completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                model="llama3-70b-8192",
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            parsed_schema = json.loads(completion.choices[0].message.content)
            print("parsed schema:", parsed_schema)

            if session_id not in self.state_dict:
                self.state_dict[session_id] = SessionState().model_dump()

            self.UpdateState_creation(session_id, user_input, parsed_schema)
            return parsed_schema

        except Exception as e:
            print(f"Error in extract_schema: {e}")
            return {"error": f"Invalid schema format {e}"}

    async def classify_query(self, query: str) -> str:
        prompt = f"""
    # Instructions:
    Classify the user's message into one of these categories:
    1. "greeting" - if it's a greeting or introduction
    2. "creation" - if the user explicitly wants to create/make something now
    3. "information" - if the user is asking how to do something or requesting information
    4. "general" - for other queries

    Return ONLY one of these words: greeting, creation, information, or general

    User message: {query}
    Classification:"""

        try:
            completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                model="llama3-70b-8192",
                temperature=0.1,
                max_tokens=10
            )

            return completion.choices[0].message.content.strip().lower()
        except Exception as e:
            print(f"Error in classify_query: {e}")
            return "general"

    async def rag(self, query: str, contexts: list, session_id: str) -> dict:
        if session_id not in self.state_dict:
            self.state_dict[session_id] = SessionState().model_dump()

        try:
            query_type = await self.classify_query(query)
            print(f"Query type: {query_type}")

            if query_type == "greeting":
                response = "Hi! How may I help you? Do you want to create something or know anything?"
                self.UpdateState(session_id, response)
                return {"response": response}

            elif query_type == "creation":
                response = await self.extract_schema(contexts, query, session_id)
                return {"response": response}

            else:  # information or general query
                prompt = f"""
        Based on the user's question, provide a helpful response. If they're asking about how to do something,
        include clear steps or requirements. Be concise but informative.

        User query: {query}
        Response:"""

                completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    model="llama3-70b-8192",
                    temperature=0.2,
                    max_tokens=1000
                )
                response = completion.choices[0].message.content
                self.UpdateState_information(session_id, response)
                return {"response": response}
        except Exception as e:
            print(f"Error in rag: {e}")
            error_response = "I apologize, but I encountered an error processing your request."
            self.UpdateState_information(session_id, error_response)
            return {"response": error_response}

obj = Agent_RAG()

@app.route("/")
def home():
    return "Welcome To RAG API!"

@app.route("/Rag", methods=['POST'])
async def handle_request():
    try:
        data = request.json
        received_message = data.get('payload', '')
        session_id = data.get('session_id', 'default_session')
        

        if not received_message:
            return Response(
                json.dumps({"error": "No message provided"}),
                mimetype='application/json',
                status=400
            )

        if session_id not in obj.state_dict:
            obj.InitiallizeState(session_id)

        obj.UpdateState_User(session_id, received_message)

        contexts = await obj.retrieve(received_message)
        result = await obj.rag(received_message, contexts, session_id)

        state = obj.getstate(session_id)
        state=state["updated_state"]
        print("*************state*************:", state)

        if session_id not in state:
            return Response(
                json.dumps({"error": "Session state not found"}),
                mimetype='application/json',
                status=404
            )

        session_state = SessionState(**state[session_id])

        return Response(
            json.dumps(session_state.model_dump()),
            mimetype='application/json'
        )
    except Exception as e:
        print(f"Error in handle_request: {e}")
        return Response(
            json.dumps({"error": str(e)}),
            mimetype='application/json',
            status=500
        )

@app.route("/getstate", methods=['GET'])
def Getstate():
    try:
        state = obj.getstate()
        print("Current state:", json.dumps(state, indent=4))

        return Response(
            json.dumps({"State": state}, indent=4),
            mimetype='application/json'
        )
    except Exception as e:
        print(f"Error in Getstate: {e}")
        return Response(
            json.dumps({"error": str(e)}),
            mimetype='application/json',
            status=500
        )

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8001)