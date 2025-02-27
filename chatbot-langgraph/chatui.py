import json
from typing import List, Optional, Union, Literal, Dict, Any
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
from langgraph.graph import MessagesState
from langgraph.checkpoint.memory import MemorySaver
import os
import streamlit as st
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import os

# Initialize LLM
os.environ["GROQ_API_KEY"] = ""
llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0
)

# Basic Models
class ManagerDecision(BaseModel):
    """Structure for LLM's decision about next steps"""
    action: Literal["planning", "collection", "end", "general_conversation"]
    status: Literal["pending", "in_progress", "completed"]
    next_step: Optional[str] = None
    next_question: Optional[str] = None
    reasoning: str
    validation_feedback: Optional[str] = None

class CampaignStep(BaseModel):
    """Simplified campaign step without validation rules"""
    task: str
    required_info: List[str]
    collected_info: Dict[str, Any] = Field(default_factory=dict)
    questions: Dict[str, str]
    last_question: Optional[str] = None
    expected_input: Optional[str] = None
    status: str = "pending"
    output: Optional[str] = None

class CampaignInfo(BaseModel):
    """Tracks overall campaign information and progress"""
    steps: Dict[str, CampaignStep]
    current_step: str
    stage: str = "planning"

class TaskState(MessagesState):
    """Main state management for the workflow"""
    conversation_id: str
    action: Optional[str]
    campaign_info: Optional[CampaignInfo]
    output: str = ""
    status: str = "pending"

class TaskIdentification(BaseModel):
    task_type: Literal["general_convo", "campaign_convo", "other_services"]
    description: str
        
        
def generate_context_summary(messages: List[HumanMessage]) -> str:
    """Generate a concise summary of the conversation context."""
    summary_prompt = """
    Summarize the following conversation in a concise way, focusing on the main points and intent:
    {conversation}
    
    Keep the summary under 100 words and capture the key elements of what has been discussed.
    """
    
    conversation_text = "\n".join([msg.content for msg in messages])
    response = llm.invoke(summary_prompt.format(conversation=conversation_text))
    return response.content.strip()

def task_identifier(state: TaskState):
    """Identifies the type of task from user input using full conversation with threshold-based summarization."""
    structured_llm = llm.with_structured_output(TaskIdentification)
    
    # Get all messages from the conversation
    all_messages = state["messages"] if state["messages"] else []
    message_count = len(all_messages)
    
    # Set threshold for when to summarize (e.g., 4 messages)
    SUMMARY_THRESHOLD = 4
    
    # Determine what to send to LLM based on threshold
    if message_count > SUMMARY_THRESHOLD:
        # Generate summary if conversation exceeds threshold
        conversation_input = generate_context_summary(all_messages)
        print(f"Conversation exceeded threshold ({SUMMARY_THRESHOLD} messages). Using summary: {conversation_input}")
    else:
        # Use full conversation if below threshold
        conversation_input = "\n".join([msg.content for msg in all_messages])
        print(f"Using full conversation ({message_count} messages): {conversation_input}")
    
    # Identify task type using either full conversation or summary
    result = structured_llm.invoke(
        f"Identify if this is a campaign-related request or general conversation based on the following:\n{conversation_input}"
    )
    print("task_identifier result:", result)

    return {
        "action": result.task_type,
        "output": f"Task identified as: {result.task_type}"
    }

def campaign_manager(state: TaskState):
    """Simplified campaign manager without validation"""
    if state["action"] == "general_convo":
        return {"action": "general_convo"}
    
    campaign_info = state.get("campaign_info")
    if not campaign_info:
        return {
            "action": "planning",
            "status": "pending"
        }

    current_step = campaign_info.steps[campaign_info.current_step]
    last_message = state["messages"][-1].content if state["messages"] else None

    if current_step.status == "waiting" and last_message:
        # Store the response directly without validation
        current_step.collected_info[current_step.last_question] = last_message

        # Check if we have all required info for this step
        missing_info = [
            info for info in current_step.required_info
            if info not in current_step.collected_info
        ]

        if not missing_info:
            # Current step is complete
            current_step.status = "completed"

            # Look for the next incomplete step
            next_incomplete_step = None
            for step_name, step in campaign_info.steps.items():
                if step_name == campaign_info.current_step:
                    continue
                if step.status != "completed":
                    next_incomplete_step = step_name
                    break

            if next_incomplete_step:
                campaign_info.current_step = next_incomplete_step
                campaign_info.steps[next_incomplete_step].status = "in_progress"
                return {
                    "action": "collection",
                    "status": "in_progress",
                    "campaign_info": campaign_info
                }
            else:
                return {
                    "action": "end",
                    "status": "completed",
                    "campaign_info": campaign_info,
                    "output": "Great! We've completed all the steps for your campaign setup."
                }
        else:
            current_step.status = "in_progress"
            return {
                "action": "collection",
                "status": "in_progress",
                "campaign_info": campaign_info
            }

def campaign_planner(state: TaskState):
    """Plans the campaign creation steps"""
    campaign_steps = {
        "segment_definition": CampaignStep(
            task="Define target segment",
            required_info=["segment_condition"],
            validation_rules={
                "segment_condition": "Must be a  condition in text "
            },
            questions={
                "segment_condition": "What conditions should be used to identify the target segment? (eg people who got revenue greater that 100 etc )"
            }
        ),
        "action_type": CampaignStep(
            task="Define campaign action",
            required_info=["action_type", "value"],
            validation_rules={
                "action_type": "Must be either 'bonus' or 'discount',it might be in sentence",
                "value": "Must contain a number, even if percentages, currency symbols, or names are included (e.g., 10%, $10, 10 dollars, 10 rupees)"
            },
            questions={
                "action_type": "What type of reward would you like to offer? (bonus/discount)",
                "value": "What should be the value of the reward? (Enter a number)"
              
            }
        ),
        "channel_strategy": CampaignStep(
            task="Define communication channels",
            required_info=["channels", "frequency"],
            validation_rules={
                "channels": "Must include word like: SMS, email, push, telegram , it might be in sentence",
                "frequency": "Must be one of: immediate, daily, weekly"
            },
            questions={
                "channels": "Which communication channels should be used? (SMS/email/push/telegram, can select multiple)",
                "frequency": "How often should messages be sent? (immediate/daily/weekly)"
            }
        ),
        "scheduling": CampaignStep(
            task="Define campaign schedule",
            required_info=["start_date", "end_date"],
            validation_rules={
            },
            questions={
                "start_date": "When should the campaign start?",
                "end_date": "when should the campaign end?"
             
            }
        )
    }

    campaign_info = CampaignInfo(
        steps=campaign_steps,
        current_step="segment_definition",
        stage="collection"
    )

    return {
        "campaign_info": campaign_info,
        "action": "collection",
        "status": "in_progress",
        "output": "Campaign plan created. Let's start by defining the target segment."
    }

def single_task_executor(state: TaskState):
    """Collects information for the current campaign step"""
    campaign_info = state["campaign_info"]
    current_step = campaign_info.steps[campaign_info.current_step]

    missing_info = [
        info for info in current_step.required_info
        if info not in current_step.collected_info
    ]
    print("CAMPAIGN_INFO_COLLECTED",campaign_info)

    collected_context = ""
    if current_step.collected_info:
        collected_context = "Information we've already collected:\n"
        for info_key, info_value in current_step.collected_info.items():
            collected_context += f"- {info_key}: {info_value}\n"

    missing_context = "Information we still need:\n"
    for info in missing_info:
        missing_context += f"- {info}: {current_step.questions[info]}\n"

    prompt = f"""
    You are a helpful marketing campaign assistant having a conversation with a user.
    We are currently working on the step: '{current_step.task}'

    CONTEXT OF OUR PROGRESS:
    {collected_context if current_step.collected_info else "This is the beginning of this step - no information collected yet."}

    NEXT INFORMATION NEEDED:
    We need to ask about: {missing_info[0]}
    Question: {current_step.questions[missing_info[0]]}

    Generate a direct, single-sentence question that:
    1. Acknowledges any previously collected information (if any exists)
    2. Clearly asks for the specific information needed
    3. Includes brief examples if necessary
    4. Must be 1-2 lines only, no lengthy explanations
    """

    next_info_key = missing_info[0] if missing_info else None

    if next_info_key:
        response = llm.invoke([SystemMessage(content=prompt)])
        formulated_question = response.content

        current_step.last_question = next_info_key
        current_step.expected_input = next_info_key
        current_step.status = "waiting"
        messages = state["messages"] + [response]
        return {
            "campaign_info": campaign_info,
            "output": formulated_question,
            "status": "waiting",
            "messages": messages
        }

def general_conversation_agent(state: TaskState):
    """Handles general conversation with the user"""
    messages = state["messages"]
    system_prompt = """You are a helpful assistant engaging in general conversation.
    Maintain a friendly and informative tone while providing relevant responses."""

    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)

    return {
        "output": response.content,
        "messages": messages + [response]
    }

def route_based_on_action(state: TaskState):
    """Routes to appropriate node based on action and status"""
    if state["action"] == "end":
        return END
    elif state["action"] == "planning":
        return "campaign_planner"
    elif state["action"] == "collection":
        return "single_task_executor"
    elif state["action"] == "general_convo":
        return "general_conversation_agent"
    else:
        return "campaign_manager"

# Build workflow graph
workflow = StateGraph(TaskState)

# Add nodes
workflow.add_node("task_identifier", task_identifier)
workflow.add_node("campaign_manager", campaign_manager)
workflow.add_node("campaign_planner", campaign_planner)
workflow.add_node("single_task_executor", single_task_executor)
workflow.add_node("general_conversation_agent", general_conversation_agent)

# Add edges
workflow.add_edge(START, "task_identifier")
workflow.add_edge("task_identifier", "campaign_manager")

# Add conditional edges
workflow.add_conditional_edges(
    "campaign_manager",
    route_based_on_action,
    {
        "campaign_planner": "campaign_planner",
        "single_task_executor": "single_task_executor",
        "general_conversation_agent": "general_conversation_agent",
        END: END
    }
)
workflow.add_edge("campaign_planner", "campaign_manager")
workflow.add_edge("single_task_executor", END)
workflow.add_edge("general_conversation_agent", END)

# Compile graph with memory
memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

# Streamlit UI functions
def initialize_session_state():
    """Initialize session state variables if they don't exist"""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = "unique_thread_1"
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "campaign_state" not in st.session_state:
        st.session_state.campaign_state = {
            "conversation_id": "unique_id",
            "messages": [],
            "action": None,
            "campaign_info": None,
            "output": "",
            "status": "pending"
        }

def get_chatbot_response(user_input: str, thread_id: str) -> Dict[str, Any]:
    """Get response from chatbot while maintaining conversation state"""
    input_message = HumanMessage(content=user_input)
    current_state = st.session_state.campaign_state
    current_state["messages"].append(input_message)
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(current_state, config)
    st.session_state.campaign_state = result
    return result

def main():
    st.title("AARYA")
    st.write("Campaign Management Bot")

    initialize_session_state()

    user_input = st.text_input("You:", "")

    if st.button("Send") and user_input:
        response = get_chatbot_response(user_input, st.session_state.thread_id)
        st.session_state.chat_history.append(("You", user_input))
        st.session_state.chat_history.append(("Bot", response.get("output", "")))

    st.subheader("Chat History")
    for role, message in st.session_state.chat_history:
        if role == "You":
            st.markdown(f"**You:** {message}")
        else:
            st.markdown(f"**Bot:** {message}")

if __name__ == "__main__":
    main()










