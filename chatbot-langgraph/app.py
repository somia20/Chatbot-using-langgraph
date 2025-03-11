from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from langchain_core.messages import HumanMessage
import os
import uvicorn
from chatui import graph, TaskState, MemorySaver
from datetime import datetime
import uuid
import requests  # Added for sending HTTP requests

app = FastAPI()

# Global state management
conversation_states = {}

class Campaign(BaseModel):
    ruleId: str
    rule: Dict[str, Any]
  

class MessagePayload(BaseModel):
    text: str

class Message(BaseModel):
    messageTime: str
    messageId: str
    source: str
    status: str
    messageType: str
    payload: MessagePayload

class Sender(BaseModel):
    name: str
    phoneNumber: str

class ChatInput(BaseModel):
    conversationId: str
    currentMessage: Message
    sender: Sender

class ResponsePayload(BaseModel):
    text: str
    campaign: Optional[Campaign] = None

class ResponsePayload2(BaseModel):
    text: str

class ResponseMessage(BaseModel):
    messageTime: str
    messageId: str
    source: str = "AI"
    status: str = "success"
    messageType: str = "text"
    payload: Union[ResponsePayload, ResponsePayload2]

class ChatOutput(BaseModel):
    currentMessage: ResponseMessage
    sender: Sender  # Include sender information

class ChatOutput2(BaseModel):
    currentMessage: ResponseMessage

def get_conversation_state(conversation_id: str) -> Dict:
    if conversation_id not in conversation_states:
        conversation_states[conversation_id] = {
            "conversation_id": conversation_id,
            "messages": [],
            "action": None,
            "campaign_info": None,
            "output": "",
            "status": "pending"
        }
    return conversation_states[conversation_id]

def update_conversation_state(conversation_id: str, new_state: Dict):
    conversation_states[conversation_id] = new_state

def send_campaign_to_external_api(campaign_message: str):
    """Send the campaign message to the external API."""
    url = "http://10.0.13.74:8004/generate"
    payload = {
        "featureId": "GET_SERVICE_DETAILS",
        "appName": "CMS",
        "username": "6D",
        "password": "6D",
        "reqTxnId": "100",
        "msgOrigin": "ORI",
        "msgDest": "DEST",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Dynamic timestamp
        "id": "",
        "ruletype": "",
        "data": {
            "ruletext": campaign_message  # Replace ruletext with the generated campaign message
        }
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
        print(f"Successfully sent campaign to {url}. Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send campaign to {url}. Error: {str(e)}")
        return None

@app.post("/chat", response_model=Union[ChatOutput, ChatOutput2])
async def chat(input: ChatInput, request: Request):
    try:
        # Print the incoming request
        print(f"Incoming Request: {await request.json()}")
        
        # Print the conversation ID from the incoming request
        print(f"Conversation ID from request: {input.conversationId}")
        
        # Check if the conversation ID is already in use
        if input.conversationId in conversation_states:
            print(f"Conversation ID {input.conversationId} is already in use.")
        else:
            print(f"Conversation ID {input.conversationId} is new.")

        current_state = get_conversation_state(input.conversationId)
        input_message = HumanMessage(content=input.currentMessage.payload.text)
        current_state["messages"].append(input_message)

        config = {"configurable": {"thread_id": input.conversationId}}
        res = graph.invoke(current_state, config)

        update_conversation_state(input.conversationId, res)

        response_status = "success" if res.get("status") == "completed" else "pending"
        print("_____________________", input.currentMessage.messageId)

        if res.get("status") == "completed":
            # Extract the campaign message from the output
            output_text = res.get("output", "")
            campaign_message = output_text.split("Here's your campaign message:")[-1].strip() if "Here’s your campaign message:" in output_text else output_text
            
            # Send the campaign message to the external API
            rule = send_campaign_to_external_api(campaign_message)
            print("_______________________",rule)

            return ChatOutput(
                currentMessage=ResponseMessage(
                    messageTime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  
                    messageId=input.currentMessage.messageId,
                    status=response_status,
                    payload=ResponsePayload(
                        text=output_text,
                        campaign=Campaign(
                            ruleId="70313",
                            rule = rule
                        )
                    )
                ),
                sender=input.sender
            )
        else:
            return ChatOutput2(
                currentMessage=ResponseMessage(
                    messageTime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    messageId=input.currentMessage.messageId,
                    status=response_status,
                    payload=ResponsePayload2(
                        text=res.get("output", "")
                    )
                )
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    if conversation_id in conversation_states:
        del conversation_states[conversation_id]
        return {"message": f"Conversation {conversation_id} deleted"}
    raise HTTPException(status_code=404, detail="Conversation not found")

@app.get("/conversations/{conversation_id}/state")
async def get_state(conversation_id: str):
    if conversation_id in conversation_states:
        return conversation_states[conversation_id]
    raise HTTPException(status_code=404, detail="Conversation not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)