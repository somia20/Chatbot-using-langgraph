# from fastapi import FastAPI, HTTPException, Request
# from pydantic import BaseModel
# from typing import List, Optional, Dict, Any, Union, cast
# from langchain_core.messages import HumanMessage
# import os
# import uvicorn
# from main import graph, initialize_campaign_info
# from datetime import datetime
# import uuid
# import requests
# import logging

# # Setup logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# app = FastAPI()

# # Global state management
# conversation_states = {}


# class Campaign(BaseModel):
#     ruleId: str
#     rule: Dict[str, Any]


# class MessagePayload(BaseModel):
#     text: str


# class Message(BaseModel):
#     messageTime: str
#     messageId: str
#     source: str
#     status: str
#     messageType: str
#     payload: MessagePayload


# class Sender(BaseModel):
#     name: str
#     phoneNumber: str


# class ChatInput(BaseModel):
#     conversationId: str
#     currentMessage: Message
#     sender: Sender


# class ResponsePayload(BaseModel):
#     text: str
#     campaign: Optional[Campaign] = None


# class ResponseMessage(BaseModel):
#     messageTime: str
#     messageId: str
#     source: str = "AI"
#     status: str = "success"
#     messageType: str = "text"
#     payload: ResponsePayload


# class ChatOutput(BaseModel):
#     currentMessage: ResponseMessage
#     sender: Sender


# def get_or_initialize_conversation_state(conversation_id: str, user_input: str) -> Dict:
#     """
#     Get existing conversation state or initialize a new one if it doesn't exist.
#     Only initializes campaign_info for new conversations.
#     """
#     if conversation_id not in conversation_states:
#         # New conversation - initialize with campaign_info
#         logger.info(f"Creating new conversation state for ID: {conversation_id}")
#         campaign_info = initialize_campaign_info()
#         conversation_states[conversation_id] = {
#             "conversation_id": conversation_id,
#             "messages": [],
#             "user_input": user_input,
#             "campaign_info": campaign_info,
#             "segment_results": [],
#             "action_results": [],
#             "channel_results": [],
#             "schedule_results": [],
#             "action": None,
#             "output": "",
#             "status": "pending"
#         }
#     else:
#         # Existing conversation - update only the user_input
#         logger.info(f"Using existing conversation state for ID: {conversation_id}")
#         conversation_states[conversation_id]["user_input"] = user_input

#     return conversation_states[conversation_id]


# def update_conversation_state(conversation_id: str, new_state: Dict):
#     """Update the stored conversation state with new state data"""
#     conversation_states[conversation_id] = new_state
#     logger.info(f"Updated state for conversation ID: {conversation_id}")


# def send_campaign_to_external_api(campaign_data: Dict[str, Any]):
#     """This function is no longer used as we get rule responses directly from campaign_manager_state"""
#     pass


# @app.post("/chat", response_model=ChatOutput)
# async def chat(input: ChatInput, request: Request):
#     try:
#         # Log the incoming request
#         request_body = await request.json()
#         logger.info(f"Incoming request for conversation ID: {input.conversationId}")

#         # Get or initialize conversation state
#         current_state = get_or_initialize_conversation_state(
#             input.conversationId,
#             input.currentMessage.payload.text
#         )

#         # Add the new message to the conversation history
#         input_message = HumanMessage(content=input.currentMessage.payload.text)
#         current_state["messages"].append(input_message)

#         # Configure thread for memory using the conversation ID
#         config = {"configurable": {"thread_id": input.conversationId}}

#         # Invoke the graph with the current state
#         try:
#             res = graph.invoke(current_state, config)
#             logger.info(f"Graph execution completed for conversation ID: {input.conversationId}")
#         except Exception as e:
#             logger.error(f"Error in graph execution: {str(e)}")
#             raise HTTPException(status_code=500, detail=f"Error processing conversation: {str(e)}")

#         # Update stored state
#         update_conversation_state(input.conversationId, res)

#         # Determine response structure
#         response_status = "success" if res.get("status") == "completed" else "pending"

#         # Handle messages properly - extract content from the last message if it's a list
#         if isinstance(res.get("messages"), list) and res["messages"]:
#             # Get the content of the last message
#             last_message = res["messages"][-1]
#             output_text = last_message.content if hasattr(last_message, "content") else str(last_message)
#         elif isinstance(res.get("messages"), str):
#             # If it's already a string, use it directly
#             output_text = res["messages"]
#         else:
#             # Fallback
#             output_text = "I'm processing your request."

#         # Check if this is a campaign response that needs to be sent to the rule service
#         campaign_data = None
#         rule_response = None

#         # Check if campaign_manager_state and rule_response exist
#         if "campaign_manager_state" in res and res["campaign_manager_state"] and \
#                 hasattr(res["campaign_manager_state"], "rule_response") and res["campaign_manager_state"].rule_response:
#             # Use the rule_response directly from campaign_manager_state
#             rule_id = res["campaign_manager_state"].campaign_name or "default_rule_id"
#             rule_response = res["campaign_manager_state"].rule_response
#             logger.info(f"Found rule_response in campaign_manager_state")
#         elif res.get("campaign_summary"):
#             try:
#                 # Extract campaign summary and send to rule service
#                 campaign_data = res.get("campaign_summary")
#                 rule_response = send_campaign_to_external_api(campaign_data)
#                 logger.info(f"Campaign sent to rule service, response: {rule_response}")
#             except Exception as e:
#                 logger.error(f"Error sending campaign to rule service: {str(e)}")
#                 # Continue without campaign data if the rule service fails

#         # Create response payload
#         payload = ResponsePayload(text=output_text)

#         # Add campaign data if available
#         if rule_response:
#             rule_id = "default_rule_id"
#             if campaign_data and "rule_id" in campaign_data:
#                 rule_id = campaign_data.get("rule_id")
#             elif "campaign_manager_state" in res and res["campaign_manager_state"] and \
#                     hasattr(res["campaign_manager_state"], "campaign_name"):
#                 rule_id = res["campaign_manager_state"].campaign_name or rule_id

#             payload.campaign = Campaign(
#                 ruleId=rule_id,
#                 rule=rule_response
#             )

#         # Create response message
#         response_message = ResponseMessage(
#             messageTime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#             messageId=input.currentMessage.messageId,
#             status=response_status,
#             payload=payload
#         )

#         # Return complete response
#         return ChatOutput(
#             currentMessage=response_message,
#             sender=input.sender
#         )

#     except HTTPException:
#         # Re-raise HTTP exceptions
#         raise
#     except Exception as e:
#         logger.error(f"Unexpected error in chat endpoint: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"An unexpected error occurred: {str(e)}"
#         )


# @app.delete("/conversations/{conversation_id}")
# async def delete_conversation(conversation_id: str):
#     if conversation_id in conversation_states:
#         del conversation_states[conversation_id]
#         logger.info(f"Deleted conversation {conversation_id}")
#         return {"message": f"Conversation {conversation_id} deleted"}
#     raise HTTPException(status_code=404, detail="Conversation not found")


# @app.get("/conversations/{conversation_id}/state")
# async def get_state(conversation_id: str):
#     if conversation_id in conversation_states:
#         return conversation_states[conversation_id]
#     raise HTTPException(status_code=404, detail="Conversation not found")


# if __name__ == "__main__":
#     # Get port from environment or use default
#     port = 9000
#     uvicorn.run(app, host="0.0.0.0", port=port)


from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union, cast
from langchain_core.messages import HumanMessage
import os
import uvicorn
from main import graph, initialize_campaign_info
from datetime import datetime
import uuid
import requests
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Global state management
conversation_states = {}


class Campaign(BaseModel):
    ruleId: str
    rule: Dict[str, Any]
    campaignName: Optional[str] = None


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


class ResponseMessage(BaseModel):
    messageTime: str
    messageId: str
    source: str = "AI"
    status: str = "success"
    messageType: str = "text"
    payload: ResponsePayload


class ChatOutput(BaseModel):
    currentMessage: ResponseMessage
    sender: Sender


def get_or_initialize_conversation_state(conversation_id: str, user_input: str) -> Dict:
    """
    Get existing conversation state or initialize a new one if it doesn't exist.
    Only initializes campaign_info for new conversations.
    """
    if conversation_id not in conversation_states:
        # New conversation - initialize with campaign_info
        logger.info(f"Creating new conversation state for ID: {conversation_id}")
        campaign_info = initialize_campaign_info()
        conversation_states[conversation_id] = {
            "conversation_id": conversation_id,
            "messages": [],
            "user_input": user_input,
            "campaign_info": campaign_info,
            "segment_results": [],
            "action_results": [],
            "channel_results": [],
            "schedule_results": [],
            "action": None,
            "output": "",
            "status": "pending"
        }
    else:
        # Existing conversation - update only the user_input
        logger.info(f"Using existing conversation state for ID: {conversation_id}")
        conversation_states[conversation_id]["user_input"] = user_input

    return conversation_states[conversation_id]


def update_conversation_state(conversation_id: str, new_state: Dict):
    """Update the stored conversation state with new state data"""
    conversation_states[conversation_id] = new_state
    logger.info(f"Updated state for conversation ID: {conversation_id}")


def send_campaign_to_external_api(campaign_data: Dict[str, Any]):
    """This function is no longer used as we get rule responses directly from campaign_manager_state"""
    pass


@app.post("/chat", response_model=ChatOutput)
async def chat(input: ChatInput, request: Request):
    try:
        # Log the incoming request
        request_body = await request.json()
        logger.info(f"Incoming request for conversation ID: {input.conversationId}")

        # Get or initialize conversation state
        current_state = get_or_initialize_conversation_state(
            input.conversationId,
            input.currentMessage.payload.text
        )

        # Add the new message to the conversation history
        input_message = HumanMessage(content=input.currentMessage.payload.text)
        current_state["messages"].append(input_message)

        # Configure thread for memory using the conversation ID
        config = {"configurable": {"thread_id": input.conversationId}}

        # Invoke the graph with the current state
        try:
            res = graph.invoke(current_state, config)
            logger.info(f"Graph execution completed for conversation ID: {input.conversationId}")
        except Exception as e:
            logger.error(f"Error in graph execution: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing conversation: {str(e)}")

        # Update stored state
        update_conversation_state(input.conversationId, res)

        # Determine response structure
        response_status = "success" if res.get("status") == "completed" else "pending"

        # Extract content from the last message if messages is a list
        messages = res.get("messages", [])
        if isinstance(messages, list) and messages:
            # Get the content of the last message
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                output_text = last_message.content
            else:
                output_text = str(last_message)
        else:
            # If messages is not a list or is empty, use it directly or default to empty string
            output_text = messages if isinstance(messages, str) else ""

        logger.info(f"Extracted output text: {output_text[:100]}...")

        # Check if campaign_manager_state and rule_response exist in the graph response
        campaign = None
        if "campaign_manager_state" in res and res["campaign_manager_state"]:
            if hasattr(res["campaign_manager_state"], "rule_response") and res["campaign_manager_state"].rule_response:
                rule_id = res["campaign_manager_state"].campaign_name or "default_rule_id"
                # Use the rule_response directly as the JSON structure for the "rule" field
                rule_response = res["campaign_manager_state"].rule_response
                logger.info(f"Found rule_response in campaign_manager_state")

                # Get campaign name if it exists
                campaign_name = None
                if hasattr(res["campaign_manager_state"], "campaign_name"):
                    campaign_name = res["campaign_manager_state"].campaign_name
                    logger.info(f"Found campaign_name in campaign_manager_state: {campaign_name}")

                # Create campaign object for response, including the campaign name
                campaign = Campaign(
                    ruleId=rule_id,
                    rule=rule_response,  # Direct assignment of the JSON structure
                    campaignName=campaign_name  # Set the campaignName field with the extracted value
                )

        # Create response payload
        payload = ResponsePayload(text=output_text, campaign=campaign)

        # Create response message
        response_message = ResponseMessage(
            messageTime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            messageId=input.currentMessage.messageId,
            status=response_status,
            payload=payload
        )

        # Return complete response
        return ChatOutput(
            currentMessage=response_message,
            sender=input.sender
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    if conversation_id in conversation_states:
        del conversation_states[conversation_id]
        logger.info(f"Deleted conversation {conversation_id}")
        return {"message": f"Conversation {conversation_id} deleted"}
    raise HTTPException(status_code=404, detail="Conversation not found")


@app.get("/conversations/{conversation_id}/state")
async def get_state(conversation_id: str):
    if conversation_id in conversation_states:
        return conversation_states[conversation_id]
    raise HTTPException(status_code=404, detail="Conversation not found")


if __name__ == "__main__":
    # Get port from environment or use default
    port = int(os.getenv("PORT", 9000))
    uvicorn.run(app, host="0.0.0.0", port=port)