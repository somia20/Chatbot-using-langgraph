from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from langchain_core.messages import HumanMessage
import os
import uvicorn
from chatui import graph, TaskState, MemorySaver
from datetime import datetime
import uuid

app = FastAPI()

# Global state management
conversation_states = {}

class Campaign(BaseModel):
    ruleId: str
    campaignName: str
    campaignType: str
    campaignStatus: str

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
        print("_____________________",input.currentMessage.messageId)
        if res.get("status") == "completed":
            return ChatOutput(
                currentMessage=ResponseMessage(
                    messageTime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  
                    messageId=input.currentMessage.messageId,
                    status=response_status,
                    payload=ResponsePayload(
                        text=res.get("output", ""),
                        campaign=Campaign(
                            ruleId="70313",
                            campaignName="Summer Promo",
                            campaignType="advertisement",
                            campaignStatus="pending"
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
    uvicorn.run(app, host="0.0.0.0", port=9000)