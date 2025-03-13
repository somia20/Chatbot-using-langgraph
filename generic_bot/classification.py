from typing import Dict, Any
from groq import Groq
from flask import Flask, request, jsonify, redirect, render_template
import asyncio
import uuid
import requests  # For making HTTP requests to the RAG endpoint
from RAG_Custom import Agent_RAG
from manager import ManagerAgent
import json
app = Flask(__name__)

# In-memory conversation history storage (stores conversation-wise history)
conversation_history: Dict[str, list] = {}

# Global state dictionary
state_dict: Dict[str, Dict[str, Any]] = {}

# Groq setup
GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY)

conversation_id = str(uuid.uuid4())
print('Conversation_id:', conversation_id)

async def classify_conversation(user_input: str) -> str:
    """
    Classify the conversation as either 'general' or 'task-related'.
    Args:
        user_input: The user's input message.
    Returns:
        str: 'general' or 'task-related'.
    """
    prompt = f"""
# Instructions:
- Analyze the user input and determine if it is a general conversation or task-related.
- Return **only one of the following** based on the classification:
  - "general" if the user input is a general conversation (e.g., greetings, casual talk).
  - "task-related" if the user input is related to a specific task or query.
- Do not include any additional text or explanations. Only return "general" or "task-related".

User Input: {user_input}

Classification:
"""
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                     {"role": "user", "content": prompt}],
            model="llama3-70b-8192",
            temperature=0.2,
            max_tokens=100
        )
        classification = completion.choices[0].message.content.strip().lower()
        print('LLM output for classification:', classification)

        # Validate the classification
        if classification not in ["general", "task-related"]:
            print(f"Invalid classification returned by LLM: {classification}")
            return "unknown"

        return classification
    except Exception as e:
        print(f"Error in classify_conversation: {e}")
        return "unknown"

async def handle_general_conversation(message: str) -> Dict[str, Any]:
    """
    Generates a response for general conversation using Groq.
    Args:
        message: User's input message.
    Returns:
        Dict: Response containing message and conversation ID.
    """

    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            prompt= """You are a friendly chatbot having a professional conversation. 
            You are a friendly chatbot who ALWAYS responds in exactly 2 sentences. 
            Your responses must be natural, direct, and conversational.
            Never use disclaimers about being an AI. Never mention limitations or capabilities. 
            Never ask more than one question back""",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.2,
            max_tokens=100
        )

        message_content = response.choices[0].message.content.strip()

        # Store this conversation in history
        if conversation_id:
            conversation_history.setdefault(conversation_id, []).append({
                "user_message": message,
                "bot_message": message_content
            })

        return {
            "message": message_content,
            "conversation_id": conversation_id
        }
    except Exception as e:
        print(f"Error in handle_general_conversation: {e}")
        return {
            "message": "Hello! Is there something I can help you with?",
            "conversation_id": None
        }


async def process_message(message: str) -> Dict[str, Any]:
    global state_dict
    print(f"current_state: {state_dict}")
    """
    Processes incoming message and routes appropriately.
    CASE 1 :-
    - If conversation_id is not present in state_dict, classify the conversation as :
      general (Classification's llm is used)
      task-related(RAG'S llm is used)

    CASE 2 :-
    - If conversation_id is present and action is False, (Then RAG's llm is used)

    CASE 3 :-
    - If conversation_id is present and  action is present, (Then Manager's llm is used)

    Args:
        message: User's input message.
    Returns:
        Dict: Response containing processing results.
    """
    response = {"output": "Unknown error occurred"}  # Default response to avoid UnboundLocalError


    # Check if conv id is present if it is not present then assign it a convo id and classify it as general or task related

    # if general then convo id is assigned only for that
    if conversation_id not in state_dict:
        # Determine if message is general conversation
        content = await classify_conversation(message)
        is_general = content == 'general'

        if is_general:
            print("classification llm is used")
            # Handle general conversation
            response_data = await handle_general_conversation(message)
            response = {
                'conversation_id': conversation_id,
                'message': message,
                'is_general': is_general,
                'output': response_data['message']
            }
            # Update the state_dict
            state_dict[conversation_id] = {
                "action": False,
                "plan": False,
                "output": False,
                "messages": {
                    "user": message,
                    "AI": response_data['message']
                }
            }
            print("State dictionary", state_dict)
        else:
            # Handle task-related conversation by calling RAG.py

            """
            contexts = await retrieve(received_message)
            result = await rag(received_message, contexts, session_id)
            """


            # obejct 1 is handling task relatd thing when  convo is not present and action is not present
            obj1 = Agent_RAG()
            print("************************************obj 1 is used")
               # Initialize state if needed
            if conversation_id not in obj1.state_dict:
                    obj1.InitiallizeState(conversation_id)

            # Update conversation history as well as state with the user's message
            obj1.UpdateState_User(conversation_id, message)

            contexts = await obj1.retrieve(message) # received_message = message
            result = await obj1.rag(message, contexts, conversation_id) # received_message = message, contexts = contexts, session_id = conversation_id
            rag_response= obj1.getstate(conversation_id)

           # when getting result from RAG(TO UPDATE THE STATE_DICT OF CLASSIFFICATION WITH RAG)
            try:
                if "action" in rag_response[conversation_id]:

                        state_dict = rag_response
                        rag_response=rag_response[conversation_id]["messages"][-1]["content"]


        # when getting result from manager (TO UPDATE THE STATE_DICT OF CLASSIFFICATION WITH MANAGER)
            except:
                if "action" in rag_response["updated_state"][conversation_id]:

                        state_dict = rag_response["updated_state"]
                        rag_response=rag_response["response"]


            response = {
                'conversation_id': conversation_id,
                'message': message,
                'is_general': is_general,
                'output': json.dumps(rag_response)
            }

    # Check if conv id is present and action is False
    elif not state_dict[conversation_id]["action"]:

        """
        contexts = await retrieve(received_message)
        result = await rag(received_message, contexts, session_id)
        """
        # obejct 2 is when convo id is present and action is false
        obj2 = Agent_RAG()
        print("**************************************************obj 2 is used")
        # Initialize state if needed
        if conversation_id not in obj2.state_dict:
                    obj2.InitiallizeState(conversation_id)

        obj2.UpdateState_User(conversation_id, message)
        contexts = await obj2.retrieve(message) # received_message = message
        result = await obj2.rag(message, contexts, conversation_id) # received_message = message, contexts = contexts, session_id = conversation_id
        rag_response= obj2.getstate(conversation_id)

     # when getting result from RAG(TO UPDATE THE STATE_DICT OF CLASSIFFICATION WITH RAG)
        try:
          if "action" in rag_response[conversation_id]:

                state_dict = rag_response
                rag_response=rag_response[conversation_id]["messages"][-1]["content"]

     # when getting result from manager (TO UPDATE THE STATE_DICT OF CLASSIFFICATION WITH MANAGER)
        except:
          if "action" in rag_response["updated_state"][conversation_id]:

                state_dict = rag_response["updated_state"]
                rag_response=rag_response["response"]



        response = {
            'conversation_id': conversation_id,
            'message': message,
            'is_general': False,
            'output': json.dumps(rag_response)
        }
        print("response",response)
    # If action present
    else:

        manager = ManagerAgent()
        print("***************************************************Manager is used")
        result = manager.update_with_user_input(state_dict,message,conversation_id)
        # state_dict = rag_response["updated_state"]
        response = {
            'conversation_id': conversation_id,
            'message': message,
            'is_general': False,
            'output': result["response"]
        }
    return response["output"]


async def execute(prompt: str) -> Dict[str, Any]:
    """
    Executes the message processing pipeline.
    Args:
        prompt: The user's input message.
    Returns:
        Dict: Response from the message processing.
    """
    response = await process_message(prompt)
    return response

@app.route('/')
def hello():
    return render_template('classification/index.html')

@app.route('/agent', methods=['GET', 'POST'])
async def send_sms():
    if request.method == 'GET':
        return render_template('classification/agent.html')

    data = request.json
    received_message = data.get('payload')
    print(f"The received message is: {received_message}")

    response = await execute(prompt=received_message)
    # print(type(response))
    # if "RoutingToRAG" in response:
    #     # Routing to RAG
    #     response = RAG().retrieve()

    return json.dumps({"message": response})
# @app.route("/RAG")
# def RAG_Custom():
#     response = RAG_Custom
#     return jsonify(response)
@app.route('/history/<conversation_id>', methods=['GET'])
def get_conversation_history(conversation_id):
    return render_template('classification/history.html', conversation_id=conversation_id)

@app.route('/session_state', methods=['GET', 'POST'])
def check_session_state():
    if request.method == 'GET':
        return render_template('classification/session.html')

    data = request.json
    conversation_id = data.get('conversation_id')

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400

    session_state = state_dict.get(conversation_id, {})

    return jsonify({"conversation_id": conversation_id, "session_state": session_state})

if __name__ == "__main__":
    print("Starting Flask application...")
    app.run(debug=True, host='0.0.0.0', port=8000)