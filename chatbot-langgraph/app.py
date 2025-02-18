from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage
import os
import uvicorn
from chatui import graph, TaskState, MemorySaver
from datetime import datetime
import uuid

app = FastAPI()

# Global state management
conversation_states = {}

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

class ResponseMessage(BaseModel):
    messageId: str
    source: str = "AI"
    status: str = "success"
    messageType: str = "text"
    payload: ResponsePayload

class ChatOutput(BaseModel):
    message: ResponseMessage

def get_conversation_state(conversation_id: str) -> Dict:
    """Retrieve or create conversation state"""
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
    """Update the stored conversation state"""
    conversation_states[conversation_id] = new_state

def generate_message_id() -> str:
    """Generate a unique message ID with the required format"""
    return f"msg_{int(datetime.now().timestamp() * 1000)}"

@app.post("/chat", response_model=ChatOutput)
async def chat(input: ChatInput):
    try:
        # Get existing state or create new one
        current_state = get_conversation_state(input.conversationId)
        
        # Add new message to existing messages
        input_message = HumanMessage(content=input.currentMessage.payload.text)
        current_state["messages"].append(input_message)
        
        # Invoke the graph with the current state
        config = {"configurable": {"thread_id": input.conversationId}}
        res = graph.invoke(current_state, config)
        
        # Update stored state
        update_conversation_state(input.conversationId, res)
        
        # Prepare the response in the required format
        response = ChatOutput(
            message=ResponseMessage(
                messageId=generate_message_id(),
                payload=ResponsePayload(
                    text=res.get("output", "")
                )
            )
        )
        
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Endpoint to clear a conversation's state"""
    if conversation_id in conversation_states:
        del conversation_states[conversation_id]
        return {"message": f"Conversation {conversation_id} deleted"}
    raise HTTPException(status_code=404, detail="Conversation not found")

@app.get("/conversations/{conversation_id}/state")
async def get_state(conversation_id: str):
    """Endpoint to get current conversation state (for debugging)"""
    if conversation_id in conversation_states:
        return conversation_states[conversation_id]
    raise HTTPException(status_code=404, detail="Conversation not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)