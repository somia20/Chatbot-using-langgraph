from models import *
from config import *
import requests
from datetime import datetime
import json


def extraction_manager(state: OverallState):
    campaign_info = state["campaign_info"]

    # If in planning stage, move to collection stage
    if state["campaign_info"].stage == "planning":
        # Create an updated campaign_info if needed (using a copy, for example)
        updated_campaign_info = state["campaign_info"].copy()  # Adjust according to your object's API
        updated_campaign_info.stage = "collection"

        # Return only the changed keys
        return {
            "action": "parallelize_extraction",
            "campaign_info": updated_campaign_info
        }

    # If in collection stage, check for pending steps
    elif campaign_info.stage == "collection":
        pending_steps = []

        # Check which steps are still pending
        for step_name, step in campaign_info.steps.items():
            if step.status != "completed":
                pending_steps.append(step_name)

        # If there are pending steps, send to follow_up node
        if pending_steps:
            print(f"Found pending steps: {pending_steps}")
            # Create a copy of campaign_info so you don't mutate the original directly
            updated_campaign_info = state["campaign_info"].copy()  # Adjust depending on your CampaignInfo API
            updated_campaign_info.stage = "waiting"
            # Return only the keys that changed
            return {
                "pending_steps": pending_steps,
                "action": "follow_up",
                "campaign_info": updated_campaign_info
            }

    # Fix the typo (original had "complected")
    campaign_info.stage = "completed"

    return {
        "action": "campaign_manager",
        "campaign_info": campaign_info
    }
def generate_campaign_message(campaign_info: CampaignInfo) -> str:
    """Generate a campaign message from collected campaign information, using only segment_definition and action_type."""
    formatted_info = "Campaign Details:\n"
    steps_to_include = ["segment_definition", "action_type"]
    for step_name in steps_to_include:
        step = campaign_info.steps.get(step_name)
        if step and step.collected_info:
            collected = step.collected_info
            formatted_info += f"- {step.task}:\n"
            for key, value in collected.items():
                formatted_info += f"  * {key}: {value}\n"

    prompt = f"""
    You are a marketing assistant tasked with creating a concise campaign announcement.
    Based on the following campaign details, generate a short, engaging message (2-3 sentences)
    that summarizes the campaign for the target audience. Keep it clear and appealing.
    Only use campaign details for generating message, do not add anything on your own.
    Just include the details.
    Keep message in one line.
    Do not add commas(,) in your generated message.
    Do not add anything extra which is not mentioned in campaign details.
    
    {formatted_info}
    """
    response = llm.invoke([SystemMessage(content=prompt)])
    return response.content.strip()

# def campaign_manager(state: OverallState):
#     print("entering campaign manager")
#     return state
# def campaign_manager(state: OverallState):
#     print("entering campaign manager")
#     campaign_info = state["campaign_info"]
    
#     # Check if all steps are completed
#     all_completed = all(step.status == "completed" for step in campaign_info.steps.values())
    
#     if all_completed and campaign_info.stage == "completed":
#         # Generate the campaign message
#         campaign_message = generate_campaign_message(campaign_info)
#         print(f"Generated campaign message: {campaign_message}")
        
#         # Prepare payload for external API call
#         payload = {
#             "featureId": "GET_SERVICE_DETAILS",
#             "appName": "CMS",
#             "username": "6D",
#             "password": "6D",
#             "reqTxnId": "100",
#             "msgOrigin": "ORI",
#             "msgDest": "DEST",
#             "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#             "id": "",
#             "ruletype": "",
#             "data": {
#                 "ruletext": campaign_message
#             }
#         }
        
#         # Make external API call
#         api_url = "http://10.0.13.74:8004/generate"
#         try:
#             response = requests.post(api_url, json=payload)
#             response.raise_for_status()  # Raise an exception for bad status codes
#             api_response = response.json()  # Assuming the API returns JSON
#             print(f"API response: {api_response}")

#             # Store both the campaign message and API response in state
#             state["messages"] = campaign_message
#             state["api_response"] = api_response
#         except requests.RequestException as e:
#             print(f"Error calling external API: {str(e)}")
#             state["messages"] = campaign_message  # Fallback to campaign message
#             state["api_response"] = {"error": str(e)}
    
#     return state


def campaign_manager(state: OverallState):
    print("Entering campaign manager")
    campaign_info = state["campaign_info"]
    print(f"------------------campaign_info: {campaign_info}")
    all_completed = all(step.status == "completed" for step in campaign_info.steps.values())
    
    if all_completed and campaign_info.stage == "completed":
        campaign_message = generate_campaign_message(campaign_info)
        print(f"Generated campaign message: {campaign_message}")
        state["messages"] = campaign_message  # Set the message for app.py to use
    
    return state

def follow_up(state: OverallState):
    campaign_info = state["campaign_info"]
    pending_steps = state.get("pending_steps", [])

    if campaign_info.stage == "waiting" and pending_steps:
        # Collect questions for all pending steps
        questions = []
        for step_name in pending_steps:
            step = campaign_info.steps[step_name]
            # For each required field that's missing, add the corresponding question
            for field in step.required_info:
                if field not in step.collected_info:
                    if field in step.questions:
                        questions.append(f"• {step.questions[field]}")

        # Create a prompt for the LLM
        prompt = f"""
        I'm helping the user create a marketing campaign, but I need more information.

        Based on what they've told me so far, I need to ask about the following:

        {chr(10).join(questions)}

        Create a friendly message asking the user for this information. Keep it concise but conversational.
        """

        # Call the LLM to generate the follow-up message
        response = llm.invoke([SystemMessage(content=prompt)])

        # Store the follow-up message in state
        state["messages"] = response.content

        # Since we're just generating a message, we can keep the stage as "waiting"
        # The next user input will need to be processed to extract the missing information

    return state


def route_based_on_action(state: OverallState):
    """Routes to appropriate node based on action and status"""
    if state["action"] == "end":
        return END
    elif state["action"] == "parallelize_extraction":
        return "parallelize_extraction"
    elif state["action"] == "campaign_manager":
        return "campaign_manager"
    elif state["action"] == "follow_up":
        return "follow_up"
    else:
        return "campaign_manager"



def generate_context_summary(messages: List[HumanMessage]) -> str:
    summary_prompt = """
    Summarize the following conversation in a concise way, focusing on the main points and intent:
    {conversation}
    Keep the summary under 100 words and capture the key elements of what has been discussed.
    """
    conversation_text = "\n".join([msg.content for msg in messages])
    response = llm.invoke(summary_prompt.format(conversation=conversation_text))
    return response.content.strip()

# def task_identifier(state: OverallState):
#     """Identifies if this is a campaign request or general conversation"""
#     structured_llm = llm.with_structured_output(TaskIdentification)

#     # Use the user input to identify the task
#     result = structured_llm.invoke(
#         f"""Identify if this is a campaign-related request or general conversation:

#         User message: {state['user_input']}

#         Respond with one of:
#         - 'campaign_convo' if it's about creating a marketing campaign
#         - 'general_convo' if it's just general conversation
#         - 'other_services' if it's about other business services
#         """
#     )

#     print(f"Task identified as: {result.task_type}")

#     if result.task_type != "campaign_convo":
#         # If not campaign related, route to a general conversation handler
#         # (not implemented in this code)
#         pass

#     # For campaign conversations, continue with the workflow
#     return state

def task_identifier(state: OverallState):
    """Identifies if this is a campaign request or general conversation"""
    structured_llm = llm.with_structured_output(TaskIdentification)

    # Ensure messages is a list, initialize if not present
    all_messages = state.get("messages", [])
    if not isinstance(all_messages, list):
        all_messages = [all_messages] if all_messages else []
    
    # Add the current user input as a message if it’s not already included
    current_input = state["user_input"]
    if not all_messages or all_messages[-1] != current_input:
        all_messages.append(HumanMessage(content=current_input))
    
    message_count = len(all_messages)
    SUMMARY_THRESHOLD = 4  # Adjust this threshold as needed

    if message_count > SUMMARY_THRESHOLD:
        conversation_input = generate_context_summary(all_messages)
        print(f"Conversation exceeded threshold ({SUMMARY_THRESHOLD} messages). Using summary: {conversation_input}")
    else:
        conversation_input = "\n".join([msg.content if isinstance(msg, HumanMessage) else str(msg) for msg in all_messages])
        print(f"Using full conversation ({message_count} messages): {conversation_input}")

    # Use the conversation input (summary or full) to identify the task
    result = structured_llm.invoke(
        f"""Identify if this is a campaign-related request or general conversation based on the following:

        Conversation: {conversation_input}

        Respond with one of:
        - 'campaign_convo' if it's about creating a marketing campaign
        - 'general_convo' if it's just general conversation
        - 'other_services' if it's about other business services

        Examples:
        - "I want a campaign with a 10% discount" -> 'campaign_convo'
        - "What’s the weather like?" -> 'general_convo'
        - "bonus" -> 'campaign_convo' (if it implies a reward in context)
        """
    )

    print(f"Task identified as: {result.task_type}")

    # Store the task type and update messages in state
    state["task_type"] = result.task_type
    state["messages"] = all_messages  # Persist the updated message history

    # Set action for routing
    if result.task_type != "campaign_convo":
        state["action"] = "general_conversation"
    else:
        state["action"] = "campaign_convo"  # Explicitly set for clarity

    return state


# Extraction functions
def extract_segments(state: ExtractState):
    """Extract segment information from user input using structured output"""
    user_input = state['user_input']

    # Create structured LLM
    structured_llm = llm.with_structured_output(SegmentExtraction)

    prompt = f"""
    Extract segment targeting information from this campaign request:
    "{user_input}"

    Look for conditions like:
    - Customer types (new, existing, etc.)
    - Revenue thresholds
    - Purchase history conditions
    - Geographic targeting

    Return the extracted segment condition as a string.
    If no segment information is found, return an empty string.

    Also return a confidence score between 0.0 and 1.0 that reflects how confident you are
    in the extracted information. Use 0.0 for no relevant information found, 
    and higher values for clearer mentions of segment conditions.
    """

    # Get structured output directly
    result = structured_llm.invoke([SystemMessage(content=prompt)])

    # Convert to dictionary
    segment_dict = result.model_dump()
    print(f"Extracted segment data: {segment_dict}")

    return {"segment_results": [segment_dict]}


def extract_actions(state: ExtractState):
    """Extract action information from user input using structured output"""
    user_input = state['user_input']

    # Create a structured LLM that returns ActionExtraction
    structured_llm = llm.with_structured_output(ActionExtraction)

    prompt = f"""
    Extract reward action information from this campaign request:
    "{user_input}"

    Look for:
    - Type of reward (bonus, discount)
    - Value amount (numbers, percentages)
    - Duration information (days)

    Also return a confidence score between 0.0 and 1.0 that reflects how confident you are
    in the extracted information. Use 0.0 for no relevant information found, 
    and higher values for clearer mentions of action information.
    """

    # Get structured output directly
    action_data = structured_llm.invoke([SystemMessage(content=prompt)])

    # Convert to dictionary
    action_dict = action_data.model_dump()
    print(f"Extracted action data: {action_dict}")

    return {"action_results": [action_dict]}


def extract_channels(state: ExtractState):
    """Extract channel information from user input using structured output"""
    user_input = state['user_input']

    # Create structured LLM
    structured_llm = llm.with_structured_output(ChannelExtraction)

    prompt = f"""
    Extract communication channel information from this campaign request:
    "{user_input}"

    Look for:
    - Communication channels (SMS, email, push, telegram)
    - Frequency (immediate, daily, weekly)

    Also return a confidence score between 0.0 and 1.0 that reflects how confident you are
    in the extracted information. Use 0.0 for no relevant information found, 
    and higher values for clearer mentions of channel information.
    """

    # Get structured output directly
    channel_data = structured_llm.invoke([SystemMessage(content=prompt)])

    # Convert to dictionary
    channel_dict = channel_data.model_dump()
    print(f"Extracted channel data: {channel_dict}")

    return {"channel_results": [channel_dict]}


def extract_schedule(state: ExtractState):
    """Extract schedule information from user input using structured output"""
    user_input = state['user_input']

    # Create structured LLM
    structured_llm = llm.with_structured_output(ScheduleExtraction)

    prompt = f"""
    Extract campaign schedule information from this campaign request:
    "{user_input}"

    Look for:
    - Start dates
    - End dates
    - Campaign duration

    Also return a confidence score between 0.0 and 1.0 that reflects how confident you are
    in the extracted information. Use 0.0 for no relevant information found, 
    and higher values for clearer mentions of schedule information.
    """

    # Get structured output directly
    schedule_data = structured_llm.invoke([SystemMessage(content=prompt)])

    # Convert to dictionary
    schedule_dict = schedule_data.model_dump()
    print(f"Extracted schedule data: {schedule_dict}")

    return {"schedule_results": [schedule_dict]}


# Working example
# def parallelize_extraction(state: OverallState):
#     """Creates parallel tasks for each extraction function"""
#     return [
#         Send("extract_segments", {"user_input": state["user_input"]}),
#         Send("extract_actions", {"user_input": state["user_input"]}),
#         Send("extract_channels", {"user_input": state["user_input"]}),
#         Send("extract_schedule", {"user_input": state["user_input"]}),
#     ]
def parallelize_extraction(state: OverallState):
    """Creates parallel tasks only for extraction functions that aren't completed yet"""
    campaign_info = state["campaign_info"]
    tasks = []

    # Only run segment extraction if segment step is not completed
    if campaign_info.steps["segment_definition"].status != "completed":
        tasks.append(Send("extract_segments", {"user_input": state["user_input"]}))

    # Only run action extraction if action step is not completed
    if campaign_info.steps["action_type"].status != "completed":
        tasks.append(Send("extract_actions", {"user_input": state["user_input"]}))

    # Only run channel extraction if channel step is not completed
    if campaign_info.steps["channel_strategy"].status != "completed":
        tasks.append(Send("extract_channels", {"user_input": state["user_input"]}))

    # # Only run schedule extraction if schedule step is not completed
    if campaign_info.steps["scheduling"].status != "completed":
        tasks.append(Send("extract_schedule", {"user_input": state["user_input"]}))

    # If no tasks were created (all steps are completed), set action to check_for_updates
    if not tasks:
        print("All extraction steps are already completed")
        return {"action": "check_for_updates"}

    return tasks


def combine_results(state: OverallState):
    """Combine all extraction results into the campaign info"""
    campaign_info = state["campaign_info"]

    # Process segment results
    segment_step = campaign_info.steps["segment_definition"]
    for result in state["segment_results"]:
        if result["confidence"] > 0.5 and result["segment_condition"]:
            # Only update if we don't already have a valid segment condition or the new one is better
            if ("segment_condition" not in segment_step.collected_info or
                    not segment_step.collected_info["segment_condition"] or
                    "empty string" in segment_step.collected_info["segment_condition"].lower()):
                segment_step.collected_info["segment_condition"] = result["segment_condition"]
                segment_step.status = "completed"

    # Process action results
    action_step = campaign_info.steps["action_type"]
    for result in state["action_results"]:
        if result["confidence"] > 0.5:
            # Only update fields if they contain meaningful data and don't overwrite existing valid data
            if result.get("action_type") and result["action_type"] and (
                    "action_type" not in action_step.collected_info or
                    not action_step.collected_info["action_type"]):
                action_step.collected_info["action_type"] = result["action_type"]

            if result.get("reward_value") and result["reward_value"] and (
                    "reward_value" not in action_step.collected_info or
                    not action_step.collected_info["reward_value"]):
                action_step.collected_info["reward_value"] = result["reward_value"]

            if result.get("duration_days") and result["duration_days"] and (
                    "duration_days" not in action_step.collected_info or
                    not action_step.collected_info["duration_days"]):
                action_step.collected_info["duration_days"] = result["duration_days"]

            # Mark as completed if all required fields are populated
            if all(field in action_step.collected_info for field in action_step.required_info):
                action_step.status = "completed"
            elif any(field in action_step.collected_info for field in action_step.required_info):
                action_step.status = "in_progress"

    # Process channel results
    channel_step = campaign_info.steps["channel_strategy"]
    for result in state["channel_results"]:
        if result["confidence"] > 0.5:
            if result.get("channels") and result["channels"] and (
                    "channels" not in channel_step.collected_info or
                    not channel_step.collected_info["channels"]):
                channel_step.collected_info["channels"] = result["channels"]

            if result.get("frequency") and result["frequency"] and (
                    "frequency" not in channel_step.collected_info or
                    not channel_step.collected_info["frequency"]):
                channel_step.collected_info["frequency"] = result["frequency"]

            # Mark as completed if all required fields are populated
            if all(field in channel_step.collected_info for field in channel_step.required_info):
                channel_step.status = "completed"
            elif any(field in channel_step.collected_info for field in channel_step.required_info):
                channel_step.status = "in_progress"

    # Process schedule results
    schedule_step = campaign_info.steps["scheduling"]
    for result in state["schedule_results"]:
        if result["confidence"] > 0.5:
            if result.get("start_date") and result["start_date"] and (
                    "start_date" not in schedule_step.collected_info or
                    not schedule_step.collected_info["start_date"]):
                schedule_step.collected_info["start_date"] = result["start_date"]

            if result.get("end_date") and result["end_date"] and (
                    "end_date" not in schedule_step.collected_info or
                    not schedule_step.collected_info["end_date"]):
                schedule_step.collected_info["end_date"] = result["end_date"]

            # Mark as completed if all required fields are populated
            if all(field in schedule_step.collected_info for field in schedule_step.required_info):
                schedule_step.status = "completed"
            elif any(field in schedule_step.collected_info for field in schedule_step.required_info):
                schedule_step.status = "in_progress"

    # Determine next step if needed
    if campaign_info.stage == "planning":
        # Find first incomplete step
        for step_name, step in campaign_info.steps.items():
            if step.status != "completed":
                campaign_info.current_step = step_name
                campaign_info.stage = "collection"
                break
        else:
            # All steps completed
            campaign_info.stage = "completed"

    return {"campaign_info": campaign_info}


def check_for_updates(state: OverallState):
    """
    Analyzes user input for potential updates to an already completed campaign.
    This function is called when all campaign steps are already completed.
    It checks if the user is trying to update specific aspects of the campaign.
    """
    user_input = state.get("user_input", "")
    campaign_info = state["campaign_info"]

    print("Checking for updates to completed campaign...")

    # Create a structured LLM to detect update intent
    structured_llm = llm.with_structured_output(UpdateIntent)

    prompt = f"""
    Analyze this user message to determine if they are trying to update 
    an existing marketing campaign that is already set up:

    "{user_input}"

    Identify which aspect of the campaign they might be trying to update:
    - segment: customer targeting conditions
    - action: reward type, value, or duration
    - channel: communication methods or frequency
    - schedule: start or end dates
    - none: not trying to update anything

    Only return 'none' if the message is clearly not trying to update any aspect.
    """

    update_intent = structured_llm.invoke([SystemMessage(content=prompt)])

    # If an update is detected, reset the status of that specific step
    if update_intent.update_type != "none":
        print(f"Detected intent to update {update_intent.update_type} with confidence {update_intent.confidence}")

        if update_intent.confidence > 0.6:
            # Map the update type to the corresponding step
            step_mapping = {
                "segment": "segment_definition",
                "action": "action_type",
                "channel": "channel_strategy",
                "schedule": "scheduling"
            }

            if update_intent.update_type in step_mapping:
                step_name = step_mapping[update_intent.update_type]
                # Reset the step status to allow re-extraction
                campaign_info.steps[step_name].status = "pending"
                print(f"Reset status of {step_name} to pending for re-extraction")

                # Update state to indicate we need to re-extract
                state["action"] = "parallelize_extraction"

                # If we were in completed stage, move back to collection
                if campaign_info.stage == "completed":
                    campaign_info.stage = "collection"

                return state

    # If no update was detected or confidence is low, just continue with campaign_manager
    state["action"] = "campaign_manager"
    return state
