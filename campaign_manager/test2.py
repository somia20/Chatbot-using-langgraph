
from main import  graph, initialize_campaign_info
import json
#--------------------------------------------------------------------------------

test4="I would like to create a ARPU enhancer campaign with arpu less than 10$ and age of network more than 1 year "
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
test = "SMS channel and 1 GB data product with 1 day validity"
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
# #--------------------------------------------------------------------------------
#
#
test = "locobait1aa"
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




print("rule response ",result["campaign_manager_state"].rule_response)


#--------------------------------------------------------------------------------
#
#
#
test = " start date is march 15 2015 end date is march 16 2015 "
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
test = " end date is march 19 2015  "
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
test = " launch the campaign  "
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


