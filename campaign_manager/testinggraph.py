from lann.main import initialize_campaign_info
from main import  graph, initialize_campaign_info
#--------------------------------------------------------------------------------

test4="i want to create a campaign for customers who generated revenue greater than hundred, give them 20% discount for 14 days, send SMS notifications daily, starting from October 1 until October 15 at 9am "
campaign_info = initialize_campaign_info()

initial_state = {
    "user_input": test4,
    "campaign_info": campaign_info,
    "segment_results": [],
    "action_results": [],
    "channel_results": [],
    "schedule_results": []
}

# Configure thread for memory
config = {"configurable": {"thread_id": "123"}}

# Run the graph
print(f"========user {test4}")
result = graph.invoke(initial_state, config)
print(f"========bot {result["messages"][-1].content}")


#--------------------------------------------------------------------------------
test = "gigachad"
print(f"========user {test}")
state_two = {
    "user_input": test,
    # "campaign_info": campaign_info,
    "segment_results": [],
    "action_results": [],
    "channel_results": [],
    "schedule_results": []
}

result = graph.invoke(state_two, config)
print(f"========bot {result["messages"][-1].content}")
#--------------------------------------------------------------------------------


test = "proceed to create campaign"
state_three = {
    "user_input": test,
    # "campaign_info": campaign_info,
    "segment_results": [],
    "action_results": [],
    "channel_results": [],
    "schedule_results": []
}
print(f"========user {test}")
result = graph.invoke(state_three, config)
print(f"========bot {result["messages"][-1].content}")

#--------------------------------------------------------------------------------
#
#
#
# test = " create the campaign "
# state_three = {
#     "user_input": test,
#     # "campaign_info": campaign_info,
#     "segment_results": [],
#     "action_results": [],
#     "channel_results": [],
#     "schedule_results": []
# }
# print(f"========user {test}")
# result = graph.invoke(state_three, config)
# print(f"========bot {result["messages"][-1].content}")
