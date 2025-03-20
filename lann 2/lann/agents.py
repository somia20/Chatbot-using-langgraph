from models import *
from config import *


def extraction_manager(state: OverallState):
    campaign_info = state["campaign_info"]
    print(f"Extraction manager: Current stage is {campaign_info.stage}")

    # If in planning stage, move to collection stage
    if state["campaign_info"].stage == "planning":
        print("Moving from planning to collection stage")
        # Create an updated campaign_info if needed (using a copy, for example)
        updated_campaign_info = state["campaign_info"].copy()  # Adjust according to your object's API
        updated_campaign_info.stage = "collection"

        # Return only the changed keys
        return {
            "action": "parallelize_extraction",
            "campaign_info": updated_campaign_info
        }

    # If in waiting stage, process the follow-up responses
    elif campaign_info.stage == "waiting":
        print("Processing follow-up response, moving back to collection stage")
        # Create a copy of campaign_info to avoid mutating the original
        updated_campaign_info = state["campaign_info"].copy()
        # Transition back to collection stage to process the new input
        updated_campaign_info.stage = "collection"

        # Return the next action and updated campaign_info
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
            print(f"Found pending steps: {pending_steps}, moving to waiting stage")
            # Create a copy of campaign_info so you don't mutate the original directly
            updated_campaign_info = state["campaign_info"].copy()  # Adjust depending on your CampaignInfo API
            updated_campaign_info.stage = "waiting"
            # Return only the keys that changed
            return {
                "pending_steps": pending_steps,
                "action": "follow_up",
                "campaign_info": updated_campaign_info
            }

    # All steps are complete, move to completed stage
    print("All steps complete, moving to completed stage")
    # Fix the typo (original had "complected")
    campaign_info.stage = "completed"

    return {
        "action": "campaign_manager",
        "campaign_info": campaign_info
    }
# Import required modules
import re
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple


def campaign_manager(state: OverallState):
    """
    Manages the campaign creation process after extraction is complete.

    This functioroviding with inputn handles multiple stages:
    1. Rule Service - Call API with segment and action info
    2. Schedule - Collect schedule type and details
    3. Campaign Name - Get and validate campaign name
    4. Finalize - Submit the complete campaign
    """
    print("Entering campaign manager")
    campaign_info = state["campaign_info"]
    user_input = state.get("user_input", "")

    # Initialize campaign_manager_stage if it doesn't exist
    if "campaign_manager_state" not in state:
        state["campaign_manager_state"] = CampaignManagerState(
            stage="rule_service"
        )

    current_stage = state["campaign_manager_state"].stage
    print(f"Current campaign manager stage: {current_stage}")

    # STAGE 1: Rule Service API Call
    # STAGE 1: Rule Service API Call
    if current_stage == "rule_service":
        print("Entering rule_service stage")
        segment_step = campaign_info.steps["segment_definition"]
        action_step = campaign_info.steps["action_type"]

        # Check if we have the required information
        if segment_step.status == "completed" and action_step.status == "completed":
            # Get segment condition and action details
            segment_condition = segment_step.collected_info.get("segment_condition", "")
            action_type = action_step.collected_info.get("action_type", "")
            reward_value = action_step.collected_info.get("reward_value", "")
            duration_days = action_step.collected_info.get("duration_days", "")

            # Format action text
            action_text = f"{action_type} of {reward_value} for {duration_days} days"

            # Create API request body
            rule_text = f"{segment_condition} will receive {action_text}"
            request_body = {
                "featureId": "GET_SERVICE_DETAILS",
                "appName": "CMS",
                "username": "6D",
                "password": "6D",
                "reqTxnId": "100",
                "msgOrigin": "ORI",
                "msgDest": "DEST",
                "timestamp": datetime.now().isoformat(),
                "id": "",
                "ruletype": "",
                "data": {
                    "ruletext": rule_text
                }
            }

            try:
                # Call rule service API
                print(f"Calling rule service with rule text: {rule_text}")
                rule_service_url = "http://10.0.13.74:8004/generate"
                response = requests.post(rule_service_url, json=request_body, timeout=15)

                # Check status code
                if response.status_code == 200:
                    # Store API response directly
                    api_response = response.json()
                    state["campaign_manager_state"].rule_response = api_response

                    # Move to campaign name stage
                    state["campaign_manager_state"].stage = "campaign_name"
                    print("Rule service API call successful. Moving to campaign name stage.")
                    state["messages"] = "Please provide a name for your campaign."
                    return state
                else:
                    # Handle non-200 status code
                    state[
                        "messages"] = f"There was an error processing your campaign rules: Status code {response.status_code}. Please try again after some time."
                    return state

            except Exception as e:
                # Handle any exceptions
                print(f"Error calling rule service API: {e}")
                state[
                    "messages"] = "There was an error processing your campaign rules. Please try again after some time."
                return state
        else:
            # Missing required information
            missing_info = []
            if segment_step.status != "completed":
                missing_info.append("target segment")
            if action_step.status != "completed":
                missing_info.append("action type")

            state["messages"] = f"I need more information about your {' and '.join(missing_info)} before I can proceed."
            return state

    # STAGE 2: Collect Schedule Information
    if current_stage == "schedule":
        print("Entering schedule stage")
        user_input = state.get("user_input", "")

        # Initialize schedule_info if it doesn't exist
        if "schedule_info" not in state["campaign_manager_state"]:
            state["campaign_manager_state"].schedule_info = ScheduleInfo(
                schedule_type=None,
                time=None,
                days_of_week=[],
                days_of_month=[],
                start_date=None,
                end_date=None,
                status="pending"
            )

        # Create structured LLM for schedule extraction
        structured_llm = llm.with_structured_output(ScheduleExtractionDetails)

        # Prepare combined information about current schedule state
        current_schedule = state["campaign_manager_state"].schedule_info
        schedule_status = []
        if current_schedule.schedule_type:
            schedule_status.append(f"Schedule type: {current_schedule.schedule_type}")
        if current_schedule.time:
            schedule_status.append(f"Time: {current_schedule.time}")
        if current_schedule.days_of_week:
            schedule_status.append(f"Days of week: {', '.join(current_schedule.days_of_week)}")
        if current_schedule.days_of_month:
            schedule_status.append(f"Days of month: {', '.join(map(str, current_schedule.days_of_month))}")
        if current_schedule.start_date:
            schedule_status.append(f"Start date: {current_schedule.start_date}")
        if current_schedule.end_date:
            schedule_status.append(f"End date: {current_schedule.end_date}")

        schedule_status_text = "\n".join(
            schedule_status) if schedule_status else "No schedule information provided yet."

        # Create detailed prompt with current state information
        prompt = f"""
          Extract campaign schedule information from this user input:
          "{user_input}"

          Current schedule information:
          {schedule_status_text}

          I need to extract or update the following schedule details:
          1. Schedule type: daily, weekly, or monthly
          2. If daily: time of day
          3. If weekly: which days of the week
          4. If monthly: which days of the month
          5. Campaign start date
          6. Campaign end date

          For any missing information that is not in the user input, keep the current values if they exist, 
          or return null/empty values. Don't make up information that isn't explicitly stated.

          For confidence score, assess how confident you are that you've correctly extracted the schedule information
          from the user input (0.0 = no relevant information found, 1.0 = very confident).
          """

        # Extract schedule information
        extracted_schedule = structured_llm.invoke([SystemMessage(content=prompt)])

        # Update schedule information with extracted data
        schedule_info = state["campaign_manager_state"].schedule_info

        # Only update fields if they contain valid new information
        if extracted_schedule.confidence > 0.5:
            if extracted_schedule.schedule_type:
                schedule_info.schedule_type = extracted_schedule.schedule_type

            if extracted_schedule.time:
                schedule_info.time = extracted_schedule.time

            if extracted_schedule.days_of_week:
                schedule_info.days_of_week = extracted_schedule.days_of_week

            if extracted_schedule.days_of_month:
                schedule_info.days_of_month = extracted_schedule.days_of_month

            if extracted_schedule.start_date:
                schedule_info.start_date = extracted_schedule.start_date

            if extracted_schedule.end_date:
                schedule_info.end_date = extracted_schedule.end_date

        # Check if we have all required schedule information based on the schedule type
        is_complete = True
        missing_info = []

        # Basic requirements
        if not schedule_info.schedule_type:
            is_complete = False
            missing_info.append("schedule type (daily, weekly, or monthly)")
        elif schedule_info.schedule_type == "daily" and not schedule_info.time:
            is_complete = False
            missing_info.append("time of day for the daily schedule")
        elif schedule_info.schedule_type == "weekly" and not schedule_info.days_of_week:
            is_complete = False
            missing_info.append("days of the week for the weekly schedule")
        elif schedule_info.schedule_type == "monthly" and not schedule_info.days_of_month:
            is_complete = False
            missing_info.append("days of the month for the monthly schedule")

        # Date requirements
        if not schedule_info.start_date:
            is_complete = False
            missing_info.append("campaign start date")
        if not schedule_info.end_date:
            is_complete = False
            missing_info.append("campaign end date")

        # Update schedule status
        if is_complete:
            schedule_info.status = "completed"
            # If we have all schedule information, move to campaign name stage
            state["campaign_manager_state"].stage = "campaign_name"
            # current_stage = "campaign_name"
            state["messages"] = "Great! Your campaign schedule has been set up. What would you like to name this campaign?"
            print("Schedule information complete. Moving to campaign name stage.")
        else:
            schedule_info.status = "in_progress"
            # Ask for missing information
            missing_info_text = ", ".join(missing_info)
            state[
                "messages"] = f"I still need some information about your campaign schedule. Please provide the {missing_info_text}."
            return state

    # STAGE 3: Collect and Validate Campaign Name
    if current_stage == "campaign_name":
        print("Entering campaign name stage")
        user_input = state.get("user_input", "")

        # Check if we already have a campaign name
        if not state["campaign_manager_state"].campaign_name:
            # Create structured LLM for campaign name extraction
            structured_llm = llm.with_structured_output(CampaignNameExtraction)

            prompt = f"""
            Extract a campaign name from this user input:
            "{user_input}"

            Look for phrases like:
            - "campaign name is X"
            - "name it X"
            - "call it X"
            - "let the campaign name be X"
            - Or just a name if it's the only content in the message

            Return the extracted campaign name and a confidence score between 0.0 and 1.0.
            Use 0.0 for no relevant information found, and higher values for clearer mentions of a campaign name.
            """

            # Extract campaign name
            extracted_name = structured_llm.invoke([SystemMessage(content=prompt)])

            # If we found a potential name with sufficient confidence, validate it
            if extracted_name.confidence > 0.5 and extracted_name.campaign_name:
                candidate_name = extracted_name.campaign_name.strip()

                # Call API to validate the campaign name
                validation_url = "/validateRule"  # Base URL would be added in production
                validation_payload = {
                    "ruleName": candidate_name,
                    "scheduled": True
                }

                try:
                    validation_url = "http://10.0.10.24:9090/Magik_3.0_Services/validateRule"
                    validation_payload = {
                        "ruleName": candidate_name,
                        "scheduled": True
                    }

                    # Make the actual API call
                    response = requests.post(validation_url, json=validation_payload, timeout=10)
                    validation_result = response.json()

                    # Check API response
                    if validation_result["operationCode"] == 0:
                        # Name is valid (doesn't exist), store it and create summary for confirmation
                        state["campaign_manager_state"].campaign_name = candidate_name

                        # Generate a summary of all campaign details for confirmation
                        summary = create_campaign_summary(candidate_name, state)

                        # Move to finalize stage
                        state["campaign_manager_state"].stage = "finalize"
                        state["messages"] = f"""
                        Great! I'll name this campaign "{candidate_name}".

                        {summary}

                        Please confirm if these details are correct or let me know what you'd like to change.
                        """
                        print(f"Campaign name '{candidate_name}' is valid. Moving to finalization stage.")
                        return state
                    else:
                        # Name exists, ask for a new one
                        state[
                            "messages"] = f"The campaign name '{candidate_name}' already exists. Please provide a different name."
                        # Stage remains as "campaign_name"
                        return state

                except Exception as e:
                    # Handle API error
                    print(f"Error validating campaign name: {e}")
                    state["messages"] = "I encountered an error validating the campaign name. Please try again."
                    return state
            else:
                # No name found with sufficient confidence, ask explicitly
                state["messages"] = "What would you like to name this campaign? Please provide a clear name."
                return state

    # STAGE 4: Finalize the Campaign
        # Replace the STAGE 4: Finalize the Campaign section with this code
        # STAGE 4: Finalize the Campaign
    if current_stage == "finalize":
        try:


            # Prepare the complete campaign data for reference (not used in API call)
            campaign_data = format_campaign_for_submission(
                state["campaign_manager_state"].campaign_name,
                campaign_info.steps["segment_definition"].collected_info,
                campaign_info.steps["action_type"].collected_info,
                campaign_info.steps["channel_strategy"].collected_info,
                state["campaign_manager_state"].schedule_info.dict(),
                state["campaign_manager_state"].rule_response.get("data", {}).get("rule_id", "")
            )

            # Get rule JSON from state["campaign_manager_state"].rule_response
            rule_dict = state["campaign_manager_state"].rule_response

            # Serialize rule_dict to a JSON string
            rule_json_str = json.dumps(rule_dict, separators=(',', ':'))

            # Construct final payload
            payload = {
                "campaignName": "MFS Promo Campaigns",
                "ruleJson": rule_json_str,
                "ruleName": state["campaign_manager_state"].campaign_name,
                "uiJson": rule_json_str,
                "fromChatbot": True
            }

            # Define headers
            headers = {
                "x-userid": "MQ==",
                "Content-Type": "application/json"
            }

            # URL to fire request
            url = "http://10.0.10.24:9090/Magik_3.0_Services/scheduleRule?featureId=SEG"

            # Send POST request
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)

            # Parse response
            response_data = response.json()

            # Check if campaign creation was successful
            if response_data.get("operationCode") == 0:
                # Store the campaign summary
                state["campaign_summary"] = campaign_data
                state["campaign_summary"]["campaign_id"] = "C" + datetime.now().strftime("%Y%m%d%H%M%S")

                # Mark the campaign as completed
                campaign_info.stage = "completed"

                # Create a user-friendly summary
                summary = create_campaign_summary(state["campaign_manager_state"].campaign_name, state)
                state[
                    "messages"] = f"✅ Campaign '{state['campaign_manager_state'].campaign_name}' has been created successfully!\n\n{summary}"
            else:
                # Handle campaign creation error
                state[
                    "messages"] = f"❌ There was an error creating your campaign: {response_data.get('message', 'Please try again later')}"

        except requests.RequestException as e:
            print(f"API request error: {str(e)}")
            state["messages"] = "❌ Failed to connect to the campaign service. Please try again later."
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            state["messages"] = "❌ Error processing the response from the campaign service."
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            state[
                "messages"] = "❌ An unexpected error occurred while creating the campaign. Please try again later."

        # Set action to end
        state["action"] = "end"
    # if current_stage == "finalize":
    #     # Prepare the complete campaign data
    #     campaign_data = format_campaign_for_submission(
    #         state["campaign_manager_state"].campaign_name,
    #         campaign_info.steps["segment_definition"].collected_info,
    #         campaign_info.steps["action_type"].collected_info,
    #         campaign_info.steps["channel_strategy"].collected_info,
    #         state["campaign_manager_state"].schedule_info.dict(),
    #         state["campaign_manager_state"].rule_response.get("data", {}).get("rule_id", "")
    #     )
    #
    #     # Make the API call to create the campaign
    #     response = submit_campaign(campaign_data)
    #
    #     # Check if campaign creation was successful
    #     if response["status"] == "success":
    #         # Store the campaign summary
    #         state["campaign_summary"] = campaign_data
    #         state["campaign_summary"]["campaign_id"] = response["data"]["campaign_id"]
    #
    #         # Mark the campaign as completed
    #         campaign_info.stage = "completed"
    #
    #         # Create a user-friendly summary
    #         summary = create_campaign_summary(state["campaign_manager_state"].campaign_name, state)
    #         state[
    #             "messages"] = f"✅ Campaign '{state['campaign_manager_state'].campaign_name}' has been created successfully!\n\n{summary}"
    #     else:
    #         # Handle campaign creation error
    #         state["messages"] = f"❌ There was an error creating your campaign: {response['message']}"
    #
    #     # Set action to end
    #     state["action"] = "end"

    return state



def format_campaign_for_submission(
        campaign_name: str,
        segment_info: Dict[str, Any],
        action_info: Dict[str, Any],
        channel_info: Dict[str, Any],
        schedule_info: Dict[str, Any],
        rule_id: str
) -> Dict[str, Any]:
    """Format campaign data for API submission."""
    # Format schedule details based on type
    schedule_details = {
        "type": schedule_info.get("schedule_type", ""),
        "start_date": schedule_info.get("start_date", ""),
        "end_date": schedule_info.get("end_date", ""),
    }

    # Add type-specific details
    if schedule_info.get("schedule_type") == "daily":
        schedule_details["time"] = schedule_info.get("time", "")
    elif schedule_info.get("schedule_type") == "weekly":
        schedule_details["days"] = schedule_info.get("days_of_week", [])
    elif schedule_info.get("schedule_type") == "monthly":
        schedule_details["days"] = schedule_info.get("days_of_month", [])

    # Build complete campaign data
    campaign_data = {
        "name": campaign_name,
        "rule_id": rule_id,
        "segment": {
            "condition": segment_info.get("segment_condition", "")
        },
        "action": {
            "type": action_info.get("action_type", ""),
            "value": action_info.get("reward_value", ""),
            "duration": action_info.get("duration_days", "")
        },
        "channel": {
            "type": channel_info.get("channels", ""),
            "frequency": channel_info.get("frequency", "")
        },
        "schedule": schedule_details,
        "created_at": datetime.now().isoformat()
    }

    return campaign_data


def submit_campaign(campaign_data: Dict[str, Any]) -> Dict[str, Any]:
    """Submit campaign to API. Returns API response."""
    # Simulate API call (in production, use requests.post)
    print(f"Submitting campaign: {campaign_data['name']}")

    # Simulated API response
    api_response = {
        "status": "success",
        "message": "Campaign created successfully",
        "data": {
            "campaign_id": "C" + datetime.now().strftime("%Y%m%d%H%M%S"),
            "name": campaign_data["name"],
            "created_at": datetime.now().isoformat()
        }
    }

    return api_response


def create_campaign_summary(campaign_name: str, state: OverallState) -> str:
    """Create a user-friendly summary of the campaign details for confirmation."""
    campaign_info = state["campaign_info"]

    # Get information from different steps
    segment_step = campaign_info.steps["segment_definition"]
    action_step = campaign_info.steps["action_type"]
    channel_step = campaign_info.steps["channel_strategy"]

    # Get schedule information
    schedule_info = state["campaign_manager_state"].schedule_info

    # Build summary
    summary = [
        f"📋 **Campaign Summary**",
        f"",
        f"**Campaign Name**: {campaign_name}",
        f"",
        f"📊 **Target Segment**: {segment_step.collected_info.get('segment_condition', 'Not specified')}",
        f"",
        f"🎁 **Reward**: {action_step.collected_info.get('action_type', 'Not specified')} of {action_step.collected_info.get('reward_value', 'Not specified')}",
        f"⏳ **Duration**: {action_step.collected_info.get('duration_days', 'Not specified')} days",
        f"",
        f"📱 **Communication**: {channel_step.collected_info.get('channels', 'Not specified')}",
        f"🔄 **Message Frequency**: {channel_step.collected_info.get('frequency', 'Not specified')}",
        f"",
    ]

    # Add schedule information
    schedule_type = schedule_info.schedule_type or "Not specified"
    summary.append(f"📅 **Schedule Type**: {schedule_type}")

    if schedule_type == "daily":
        summary.append(f"⏰ **Time**: {schedule_info.time or 'Not specified'}")
    elif schedule_type == "weekly":
        days = ", ".join(schedule_info.days_of_week) if schedule_info.days_of_week else "Not specified"
        summary.append(f"📆 **Days**: {days}")
    elif schedule_type == "monthly":
        days = ", ".join(
            [str(d) for d in schedule_info.days_of_month]) if schedule_info.days_of_month else "Not specified"
        summary.append(f"📆 **Days of Month**: {days}")

    summary.extend([
        f"🗓️ **Start Date**: {schedule_info.start_date or 'Not specified'}",
        f"🗓️ **End Date**: {schedule_info.end_date or 'Not specified'}",
        f"",
    ])

    return "\n".join(summary)


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
    elif state["action"] == "confirmation":  # Add this new condition
        return "campaign_manager"  # This will route back to campaign_manager which handles the confirmation stage
    else:
        return "campaign_manager"


def task_identifier(state: OverallState):
    """Identifies if this is a campaign request or general conversation"""
    structured_llm = llm.with_structured_output(TaskIdentification)

    # Use the user input to identify the task
    result = structured_llm.invoke(
        f"""Identify if this is a campaign-related request or general conversation:

        User message: {state['user_input']}

        Respond with one of:
        - 'campaign_convo' if it's about creating a marketing campaign
        - 'general_convo' if it's just general conversation
        - 'other_services' if it's about other business services
        """
    )

    print(f"Task identified as: {result.task_type}")

    if result.task_type != "campaign_convo":
        # If not campaign related, route to a general conversation handler
        # (not implemented in this code)
        pass

    # For campaign conversations, continue with the workflow
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
    # if campaign_info.steps["scheduling"].status != "completed":
    #     tasks.append(Send("extract_schedule", {"user_input": state["user_input"]}))

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
    # schedule_step = campaign_info.steps["scheduling"]
    # for result in state["schedule_results"]:
    #     if result["confidence"] > 0.5:
    #         if result.get("start_date") and result["start_date"] and (
    #                 "start_date" not in schedule_step.collected_info or
    #                 not schedule_step.collected_info["start_date"]):
    #             schedule_step.collected_info["start_date"] = result["start_date"]
    #
    #         if result.get("end_date") and result["end_date"] and (
    #                 "end_date" not in schedule_step.collected_info or
    #                 not schedule_step.collected_info["end_date"]):
    #             schedule_step.collected_info["end_date"] = result["end_date"]
    #
    #         # Mark as completed if all required fields are populated
    #         if all(field in schedule_step.collected_info for field in schedule_step.required_info):
    #             schedule_step.status = "completed"
    #         elif any(field in schedule_step.collected_info for field in schedule_step.required_info):
    #             schedule_step.status = "in_progress"

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


def create_campaign_confirmation_summary(campaign_name: str, state: OverallState) -> str:
    """Create a user-friendly summary of the campaign details for confirmation."""
    campaign_info = state["campaign_info"]

    # Get information from different steps
    segment_step = campaign_info.steps["segment_definition"]
    action_step = campaign_info.steps["action_type"]
    channel_step = campaign_info.steps["channel_strategy"]

    # Get schedule information
    schedule_info = state["campaign_manager_state"].schedule_info

    # Build summary
    summary = [
        f"📋 **Campaign Summary**",
        f"",
        f"**Campaign Name**: {campaign_name}",
        f"",
        f"📊 **Target Segment**: {segment_step.collected_info.get('segment_condition', 'Not specified')}",
        f"",
        f"🎁 **Reward**: {action_step.collected_info.get('action_type', 'Not specified')} of {action_step.collected_info.get('reward_value', 'Not specified')}",
        f"⏳ **Duration**: {action_step.collected_info.get('duration_days', 'Not specified')} days",
        f"",
        f"📱 **Communication**: {channel_step.collected_info.get('channels', 'Not specified')}",
        f"🔄 **Message Frequency**: {channel_step.collected_info.get('frequency', 'Not specified')}",
        f"",
    ]

    # Add schedule information
    schedule_type = schedule_info.schedule_type or "Not specified"
    summary.append(f"📅 **Schedule Type**: {schedule_type}")

    if schedule_type == "daily":
        summary.append(f"⏰ **Time**: {schedule_info.time or 'Not specified'}")
    elif schedule_type == "weekly":
        days = ", ".join(schedule_info.days_of_week) if schedule_info.days_of_week else "Not specified"
        summary.append(f"📆 **Days**: {days}")
    elif schedule_type == "monthly":
        days = ", ".join(
            [str(d) for d in schedule_info.days_of_month]) if schedule_info.days_of_month else "Not specified"
        summary.append(f"📆 **Days of Month**: {days}")

    summary.extend([
        f"🗓️ **Start Date**: {schedule_info.start_date or 'Not specified'}",
        f"🗓️ **End Date**: {schedule_info.end_date or 'Not specified'}",
        f"",
        f"Please confirm if these details are correct or let me know what you'd like to change."
    ])

    return "\n".join(summary)


