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
import json
import time
from logging.handlers import TimedRotatingFileHandler
import pathlib

# Create logs directory if it doesn't exist
log_dir = pathlib.Path("log")
log_dir.mkdir(exist_ok=True)

# Configure request/response logger
request_logger = logging.getLogger("request_response_logger")
request_logger.setLevel(logging.INFO)

# Create a timed rotating file handler that rotates daily
log_file_path = log_dir / "campaign_api.log"
file_handler = TimedRotatingFileHandler(
    filename=log_file_path,
    when="midnight",
    interval=1,
    backupCount=30  # Keep logs for 30 days
)


# Define log format for JSON
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage()
        }

        # Add any extra attributes that were passed to the logger
        if hasattr(record, 'request_data'):
            log_data['request_data'] = record.request_data
        if hasattr(record, 'response_data'):
            log_data['response_data'] = record.response_data
        if hasattr(record, 'conversation_id'):
            log_data['conversation_id'] = record.conversation_id

        return json.dumps(log_data)


# Set the formatter for the file handler
file_handler.setFormatter(JsonFormatter())
request_logger.addHandler(file_handler)

# Setup application logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Global state management
conversation_states = {}


class Campaign(BaseModel):
    ruleId: str
    rule: Dict[str, Any]
    campaignName: Optional[str] = None
    launch_campaign: Optional[str] = "false"
    rule_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


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


def log_request(conversation_id: str, request_data: Dict):
    """Log incoming request data"""
    log_record = logging.LogRecord(
        name=request_logger.name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Incoming request",
        args=(),
        exc_info=None
    )
    log_record.request_data = request_data
    log_record.conversation_id = conversation_id
    request_logger.handle(log_record)


def log_response(conversation_id: str, response_data: Dict):
    """Log outgoing response data"""
    log_record = logging.LogRecord(
        name=request_logger.name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Outgoing response",
        args=(),
        exc_info=None
    )
    log_record.response_data = response_data
    log_record.conversation_id = conversation_id
    request_logger.handle(log_record)


@app.post("/chat", response_model=ChatOutput)
async def chat(input: ChatInput, request: Request):
    start_time = time.time()
    try:
        # Log the incoming request
        request_body = await request.json()
        log_request(input.conversationId, request_body)

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
                launch_campaign = "false"
                if hasattr(res["campaign_manager_state"], "campaign_name"):
                    campaign_name = res["campaign_manager_state"].campaign_name
                    launch_campaign = res["campaign_manager_state"].launch_campaign
                    logger.info(f"Found campaign_name in campaign_manager_state: {campaign_name}")
                if hasattr(res["campaign_manager_state"], "launch_campaign"):
                    launch_campaign = res["campaign_manager_state"].launch_campaign
                    logger.info(f"Found launch_campaign in campaign_manager_state: {launch_campaign}")

                if launch_campaign == "false":
                    campaign_name = ""
                else:
                    campaign_name = "MFS Promo Campaigns"
                # Create campaign object for response, including the campaign name
                campaign = Campaign(
                    ruleId=rule_id,
                    rule=rule_response,  # Direct assignment of the JSON structure
                    campaignName=campaign_name,
                    rule_name=res["campaign_manager_state"].campaign_name,
                    launch_campaign=launch_campaign,
                    start_date = res["campaign_manager_state"].schedule_info.start_date,
                    end_date = res["campaign_manager_state"].schedule_info.end_date# Set the campaignName field with the extracted value
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

        # Prepare final response
        final_response = ChatOutput(
            currentMessage=response_message,
            sender=input.sender
        )

        # Log the response
        log_response(input.conversationId, final_response.dict())

        # Calculate and log processing time
        processing_time = time.time() - start_time
        logger.info(f"Request processed in {processing_time:.2f} seconds")

        return final_response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        error_response = {
            "error": str(e),
            "status": "error",
            "conversation_id": getattr(input, "conversationId", "unknown")
        }
        log_record = logging.LogRecord(
            name=request_logger.name,
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error processing request",
            args=(),
            exc_info=None
        )
        log_record.error_data = error_response
        request_logger.handle(log_record)

        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    if conversation_id in conversation_states:
        del conversation_states[conversation_id]
        logger.info(f"Deleted conversation {conversation_id}")

        # Log the deletion event
        log_record = logging.LogRecord(
            name=request_logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=f"Conversation deleted",
            args=(),
            exc_info=None
        )
        log_record.conversation_id = conversation_id
        request_logger.handle(log_record)

        return {"message": f"Conversation {conversation_id} deleted"}
    raise HTTPException(status_code=404, detail="Conversation not found")


@app.get("/conversations/{conversation_id}/state")
async def get_state(conversation_id: str):
    if conversation_id in conversation_states:
        # Log the state retrieval
        log_record = logging.LogRecord(
            name=request_logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=f"Conversation state retrieved",
            args=(),
            exc_info=None
        )
        log_record.conversation_id = conversation_id
        request_logger.handle(log_record)

        return conversation_states[conversation_id]
    raise HTTPException(status_code=404, detail="Conversation not found")


if __name__ == "__main__":
    # Get port from environment or use default
    port = 9000
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)