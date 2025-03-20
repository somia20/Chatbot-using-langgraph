#INITIAL ONE 

# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from typing import Optional
# from datetime import datetime
# from workflow import process_user_input  # Import your existing workflow function

# # Initialize FastAPI app
# app = FastAPI()

# # Define request models
# class Payload(BaseModel):
#     text: str

# class CurrentMessage(BaseModel):
#     messageTime: datetime
#     messageId: str
#     source: str
#     status: str
#     messageType: str
#     payload: Payload

# class Sender(BaseModel):
#     name: str
#     phoneNumber: str

# class ConversationRequest(BaseModel):
#     conversationId: str
#     currentMessage: CurrentMessage
#     sender: Sender

# # Define response models
# class CampaignStepResponse(BaseModel):
#     task: str
#     required_info: list
#     collected_info: dict
#     status: str

# class CampaignInfoResponse(BaseModel):
#     steps: dict[str, CampaignStepResponse]
#     current_step: str
#     stage: str

# class ConversationResponse(BaseModel):
#     conversationId: str
#     campaign_info: CampaignInfoResponse
#     message: str

# # Endpoint to handle the conversation
# @app.post("/process_conversation", response_model=ConversationResponse)
# async def process_conversation(request: ConversationRequest):
#     try:
#         # Extract the user input from the request
#         user_input = request.currentMessage.payload.text

#         # Use your existing workflow to process the user input
#         campaign_info = process_user_input(user_input, thread_id=request.conversationId)

#         # Prepare the response
#         response = {
#             "conversationId": request.conversationId,
#             "campaign_info": {
#                 "steps": {
#                     step_name: {
#                         "task": step.task,
#                         "required_info": step.required_info,
#                         "collected_info": step.collected_info,
#                         "status": step.status,
#                     }
#                     for step_name, step in campaign_info.steps.items()
#                 },
#                 "current_step": campaign_info.current_step,
#                 "stage": campaign_info.stage,
#             },
#             "message": "Message processed successfully",
#         }

#         return response

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # Run the FastAPI app
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)


#---------------------------------------------------------------------------------------------------------------
#Getting generated message in response


# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from typing import Dict, Optional
# from datetime import datetime
# import uuid
# from workflow import process_user_input, graph  # Import graph for direct state access if needed

# app = FastAPI()

# # Request Models
# class Payload(BaseModel):
#     text: str

# class CurrentMessage(BaseModel):
#     messageTime: str
#     messageId: str
#     source: str
#     status: str
#     messageType: str
#     payload: Payload

# class Sender(BaseModel):
#     name: str
#     phoneNumber: str

# class RequestBody(BaseModel):
#     conversationId: str
#     currentMessage: CurrentMessage
#     sender: Sender

# # Response Models
# class ResponsePayload(BaseModel):
#     text: str

# class ResponseMessage(BaseModel):
#     messageTime: str
#     messageId: str
#     source: str
#     status: str
#     messageType: str
#     payload: ResponsePayload

# class ResponseBody(BaseModel):
#     currentMessage: ResponseMessage

# # Helper function to generate current timestamp
# def get_current_timestamp():
#     return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# # FastAPI Endpoint
# @app.post("/campaign", response_model=ResponseBody)
# async def create_campaign(request: RequestBody):
#     try:
#         user_input = request.currentMessage.payload.text
#         thread_id = request.conversationId
#         campaign_info = process_user_input(user_input, thread_id)
#         config = {"configurable": {"thread_id": thread_id}}
#         state = graph.get_state(config).values
        
#         response_text = ""
#         status = "pending"

#         if state.get("action") == "general_conversation":
#             response_text = state.get("messages", "This doesn't seem like a campaign request. How can I assist you?")
#             if isinstance(response_text, list):
#                 response_text = response_text[-1].content if response_text else "How can I assist you?"
#             status = "success"
#         else:
#             pending_steps = [step_name for step_name, step in campaign_info.steps.items() if step.status != "completed"]
#             if pending_steps:
#                 if "messages" in state and state["messages"]:
#                     response_text = state["messages"] if isinstance(state["messages"], str) else state["messages"][-1].content
#                 if not response_text:
#                     questions = []
#                     for step_name in pending_steps:
#                         step = campaign_info.steps[step_name]
#                         for field in step.required_info:
#                             if field not in step.collected_info:
#                                 if field in step.questions:
#                                     questions.append(f"• {step.questions[field]}")
#                     response_text = "Hey there! I need a bit more info to set up your campaign. " + " ".join(questions)
#                 status = "pending"
#             else:
#                 # Use the campaign message from state if available
#                 response_text = state.get("messages", "Campaign setup is complete! Anything else you'd like to adjust?")
#                 if isinstance(response_text, list):
#                     response_text = response_text[-1].content if response_text else "Campaign setup is complete!"
#                 status = "success"

#         response = ResponseBody(
#             currentMessage=ResponseMessage(
#                 messageTime=get_current_timestamp(),
#                 messageId=request.currentMessage.messageId,
#                 source="AI",
#                 status=status,
#                 messageType="text",
#                 payload=ResponsePayload(text=response_text)
#             )
#         )
#         return response
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
# # Run the app (for testing locally)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)

#---------------------------------------------------------------------------------------------------------------

#  CURRENT ONE MADE TWO RESPONSE MODEL ONE FOR SUCCESS ONE FOR PENDING

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, Union
from datetime import datetime
import uuid
import requests
from workflow import process_user_input, graph

app = FastAPI()

# Request Models (unchanged)
class Payload(BaseModel):
    text: str

class CurrentMessage(BaseModel):
    messageTime: str
    messageId: str
    source: str
    status: str
    messageType: str
    payload: Payload

class Sender(BaseModel):
    name: str
    phoneNumber: str

class RequestBody(BaseModel):
    conversationId: str
    currentMessage: CurrentMessage
    sender: Sender

# Response Models
class Campaign(BaseModel):
    ruleId: str
    rule: Dict

# For completed: includes text and campaign
class ResponsePayload(BaseModel):
    text: str
    campaign: Optional[Campaign] = None

# For pending: only text
class ResponsePayload2(BaseModel):
    text: str

# For completed/success: includes sender
class ResponseMessage(BaseModel):
    messageTime: str
    messageId: str
    source: str
    status: str
    messageType: str
    payload: ResponsePayload
    sender: Sender

# For pending: no sender
class ResponseMessage2(BaseModel):
    messageTime: str
    messageId: str
    source: str
    status: str
    messageType: str
    payload: ResponsePayload2

# Two response types
class ResponseBody(BaseModel):  # For completed/success
    currentMessage: ResponseMessage

class ResponseBody2(BaseModel):  # For pending
    currentMessage: ResponseMessage2

def get_current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "id": "",
        "ruletype": None,
        "data": {
            "ruletext": campaign_message
        }
    }
    try:
        print(f"Sending request to {url} with payload: {payload}")
        response = requests.post(url, json=payload)
        response.raise_for_status()
        api_response = response.json()
        print(f"Received API response: {api_response}")
        return api_response
    except requests.exceptions.RequestException as e:
        print(f"Failed to send campaign to {url}. Error: {str(e)}")
        error_response = {
            "error": "API request failed",
            "details": str(e)
        }
        return error_response

@app.post("/campaign", response_model=Union[ResponseBody, ResponseBody2])
async def create_campaign(request: RequestBody):
    try:
        user_input = request.currentMessage.payload.text
        thread_id = request.conversationId

        print(f"------------------current msgId: {request.currentMessage.messageId}")

        campaign_info = process_user_input(user_input, thread_id)
       
        config = {"configurable": {"thread_id": thread_id}}
        state = graph.get_state(config).values
        
        response_text = ""
        status = "pending"

        if state.get("action") == "general_conversation":
            response_text = state.get("messages", "This doesn't seem like a campaign request. How can I assist you?")
            if isinstance(response_text, list):
                response_text = response_text[-1].content if response_text else "How can I assist you?"
            status = "success"
        else:
            pending_steps = [step_name for step_name, step in campaign_info.steps.items() if step.status != "completed"]
            if pending_steps:
                if "messages" in state and state["messages"]:
                    response_text = state["messages"] if isinstance(state["messages"], str) else state["messages"][-1].content
                if not response_text:
                    questions = []
                    for step_name in pending_steps:
                        step = campaign_info.steps[step_name]
                        for field in step.required_info:
                            if field not in step.collected_info:
                                if field in step.questions:
                                    questions.append(f"* {step.questions[field]}")
                    response_text = "Hey there! I need a bit more info to set up your campaign.\n\n" + "\n".join(questions)
                status = "pending"
            else:
                # Campaign is complete
                response_text = state.get("messages", "Campaign setup is complete! Anything else you'd like to adjust?")
                status = "completed"

        # Build the response based on status
        if status == "completed":
            # Use the campaign message from state["messages"] for text
            campaign_message = state.get("messages")
            if isinstance(campaign_message, list):
                campaign_message = campaign_message[-1].content if campaign_message else "Default campaign message"
            elif not isinstance(campaign_message, str):
                campaign_message = "Default campaign message"
            
            # Send to external API
            api_response = send_campaign_to_external_api(campaign_message)
           
            
            if api_response is not None:
                rule = api_response
            else:
                rule = {"error": "Failed to register campaign with external service"}
            print("___________________api_response",rule)

            return ResponseBody(
                currentMessage=ResponseMessage(
                    messageTime=get_current_timestamp(),
                    messageId=request.currentMessage.messageId,
                    source="AI",
                    status=status,
                    messageType="text",
                    payload=ResponsePayload(
                        text=campaign_message,
                        campaign=Campaign(
                            ruleId="70313",
                            rule=rule
                        )
                    ),
                    sender=request.sender
                )
            )
        else:
            # For pending or success, use simpler structure without sender
            return ResponseBody2(
                currentMessage=ResponseMessage2(
                    messageTime=get_current_timestamp(),
                    messageId=request.currentMessage.messageId,
                    source="AI",
                    status=status,
                    messageType="text",
                    payload=ResponsePayload2(
                        text=response_text
                    )
                )
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)