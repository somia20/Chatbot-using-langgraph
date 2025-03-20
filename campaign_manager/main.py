# Create the campaign info structure
from models import *
from agents import *
from config import *


def initialize_campaign_info():
    campaign_steps = {
        "segment_definition": CampaignStep(
            task="Define target segment",
            required_info=["segment_condition"],
            validation_rules={
                "segment_condition": "Must be a condition in text"
            },
            questions={
                "segment_condition": "Who would you like to target with this campaign?"
            }
        ),
        "action_type": CampaignStep(
            task="Define campaign action",
            required_info=["action_type"],
            validation_rules={
                "action_type": "it can be a  a product ",

            },
            questions={
                "action_type": "What reward would you like to offer?"
            }
        ),
        "channel_strategy": CampaignStep(
            task="Define communication channels",
            required_info=["channels"],
            validation_rules={
                "channels": "Must include word like: SMS, email, push, telegram, it might be in sentence",
                "channels": "Must be one of: immediate, daily, weekly , it might be in sentence"
            },
            questions={
                "channels": "How would you like to communicate with customers? (channel "
            }
        )
    }

    return CampaignInfo(
        steps=campaign_steps,
        current_step="segment_definition",
        stage="planning"
    )

# Build workflow graph
workflow = StateGraph(OverallState)

# Add nodes
workflow.add_node("task_identifier", task_identifier)
workflow.add_node("extraction_manager", extraction_manager)
workflow.add_node("parallelize_extraction", lambda x: x)  # Placeholder node
workflow.add_node("extract_segments", extract_segments)
workflow.add_node("extract_actions", extract_actions)
workflow.add_node("extract_channels", extract_channels)
workflow.add_node("extract_schedule", extract_schedule)
workflow.add_node("combine_results", combine_results)
workflow.add_node("campaign_manager", campaign_manager)
workflow.add_node("follow_up", follow_up)
workflow.add_node("check_for_updates", check_for_updates)
# Add edges
workflow.add_edge(START, "task_identifier")
workflow.add_edge('task_identifier', "extraction_manager")
workflow.add_conditional_edges(
    "extraction_manager",
    route_based_on_action,
    {
        "parallelize_extraction": "parallelize_extraction",
        "campaign_manager": "campaign_manager",
        "follow_up": "follow_up"
    }
)
# workflow.add_conditional_edges(
#     "parallelize_extraction",
#     parallelize_extraction,
#     ["extract_segments", "extract_actions", "extract_channels", "extract_schedule"]
# )
def route_from_extraction(state):
    if "action" in state and state["action"] == "check_for_updates":
        return "check_for_updates"
    else:
        return parallelize_extraction(state)

workflow.add_conditional_edges(
    "parallelize_extraction",
    route_from_extraction,
    {
        "check_for_updates": "check_for_updates",
        "extract_segments": "extract_segments",
        "extract_actions": "extract_actions",
        "extract_channels": "extract_channels",
        "extract_schedule": "extract_schedule"
    }
)
workflow.add_edge("check_for_updates", "extraction_manager")
workflow.add_edge("extract_segments", "combine_results")
workflow.add_edge("extract_actions", "combine_results")
workflow.add_edge("extract_channels", "combine_results")
workflow.add_edge("extract_schedule", "combine_results")
workflow.add_edge("combine_results", "extraction_manager")



# Compile graph with memory
memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)


# Example usage
def process_user_input(user_input, thread_id="default_thread"):
    """Process user input and update campaign info"""
    campaign_info = initialize_campaign_info()

    initial_state = {
        "user_input": user_input,
        "campaign_info": campaign_info,
        "segment_results": [],
        "action_results": [],
        "channel_results": [],
        "schedule_results": []
    }

    # Configure thread for memory
    config = {"configurable": {"thread_id": thread_id}}

    # Run the graph
    result = graph.invoke(initial_state, config)

    return result["campaign_info"]


# test4 = "i want to create a campaign for customers who generated revenue greater than hundred, give them 20% discount for 14 days, send SMS notifications daily, starting from October 1 until October 15"
# result4 = process_user_input(test4, "thread4")

# test4 = "i want to create a campaign for customers who generated revenue greater than hundred, give them 20% discount for 14 days, send SMS notifications daily"
# result4 = process_user_input(test4, "thread4")
#
# #testing
# test4="i want to create a campaign for customers who generated revenue greater than hundred, give them 20% discount for 14 days, send SMS notifications daily"
# campaign_info = initialize_campaign_info()
#
# initial_state = {
#     "user_input": test4,
#     "campaign_info": campaign_info,
#     "segment_results": [],
#     "action_results": [],
#     "channel_results": [],
#     "schedule_results": []
# }
#
# # Configure thread for memory
# config = {"configurable": {"thread_id": "123"}}
#
# # Run the graph
# print("providing with input  xegement action and channel ")
# result1 = graph.invoke(initial_state, config)
#
# test5 = "let the sheduling be starting from October 1 until October 15 at morning 9 am "
# state_two = {
#     "user_input": test5,
#     # "campaign_info": campaign_info,
#     "segment_results": [],
#     "action_results": [],
#     "channel_results": [],
#     "schedule_results": []
# }
# print("providing with input  sheduling details  ")
# result2 = graph.invoke(state_two, config)
# print(result2)
#
#
# print("providing with input  campaign name ")
# test6 = "l giga chaf "
# state_three = {
#     "user_input": test6,
#     # "campaign_info": campaign_info,
#     "segment_results": [],
#     "action_results": [],
#     "channel_results": [],
#     "schedule_results": []
# }
# result3 = graph.invoke(state_three, config)
# print(result3)
#


#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

