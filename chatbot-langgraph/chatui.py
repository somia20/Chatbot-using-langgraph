import json
from typing import List, Optional, Union, Literal, Dict, Any
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.graph import MessagesState
from langgraph.checkpoint.memory import MemorySaver
import os
import streamlit as st

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

# Helper function to generate campaign message
def generate_campaign_message(campaign_info: CampaignInfo) -> str:
    """Generate a campaign message from collected campaign information."""
    formatted_info = "Campaign Details:\n"
    for step_name, step in campaign_info.steps.items():
        collected = step.collected_info
        formatted_info += f"- {step.task}:\n"
        for key, value in collected.items():
            formatted_info += f"  * {key}: {value}\n"

    prompt = f"""
    You are a marketing assistant tasked with creating a concise campaign announcement.
    Based on the following campaign details, generate a short, engaging message (2-3 sentences)
    that summarizes the campaign for the target audience. Keep it clear and appealing.
    Only use campaign details for generating message, do not add anything on your own.
    Keep message in one line.
    
    {formatted_info}
    """
    response = llm.invoke([SystemMessage(content=prompt)])
    return response.content.strip()

# Core Functions
def generate_context_summary(messages: List[HumanMessage]) -> str:
    summary_prompt = """
    Summarize the following conversation in a concise way, focusing on the main points and intent:
    {conversation}
    Keep the summary under 100 words and capture the key elements of what has been discussed.
    """
    conversation_text = "\n".join([msg.content for msg in messages])
    response = llm.invoke(summary_prompt.format(conversation=conversation_text))
    return response.content.strip()

def task_identifier(state: TaskState):
    structured_llm = llm.with_structured_output(TaskIdentification)
    all_messages = state["messages"] if state["messages"] else []
    message_count = len(all_messages)
    SUMMARY_THRESHOLD = 4
    
    if message_count > SUMMARY_THRESHOLD:
        conversation_input = generate_context_summary(all_messages)
        print(f"Conversation exceeded threshold ({SUMMARY_THRESHOLD} messages). Using summary: {conversation_input}")
    else:
        conversation_input = "\n".join([msg.content for msg in all_messages])
        print(f"Using full conversation ({message_count} messages): {conversation_input}")
    
    result = structured_llm.invoke(
        f"Identify if this is a campaign-related request or general conversation based on the following:\n{conversation_input}"
    )
    print("task_identifier result:", result)
    return {
        "action": result.task_type,
        "output": f"Task identified as: {result.task_type}"
    }

def campaign_manager(state: TaskState):
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
        current_step.collected_info[current_step.last_question] = last_message
        print("UPDATED COLLECTED_INFO:", current_step.collected_info)

        missing_info = [
            info for info in current_step.required_info
            if info not in current_step.collected_info
        ]

        if not missing_info:
            current_step.status = "completed"
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
                campaign_message = generate_campaign_message(campaign_info)
                return {
                    "action": "end",
                    "status": "completed",
                    "campaign_info": campaign_info,
                    "output": f"Great! We've completed all the steps for your campaign setup.\n\nHere’s your campaign message:\n{campaign_message}"
                }
        else:
            current_step.status = "in_progress"
            return {
                "action": "collection",
                "status": "in_progress",
                "campaign_info": campaign_info
            }

def campaign_planner(state: TaskState):
    campaign_steps = {
        "segment_definition": CampaignStep(
            task="Define target segment",
            required_info=["segment_condition"],
            questions={
                "segment_condition": "What conditions should be used to identify the target segment? (eg people who got revenue greater that 100 etc )"
            }
        ),
        "action_type": CampaignStep(
            task="Define campaign action",
            required_info=["action_type", "value"],
            questions={
                "action_type": "What type of reward would you like to offer? (bonus/discount)",
                "value": "What should be the value of the reward? (Enter a number)"
            }
        ),
        "channel_strategy": CampaignStep(
            task="Define communication channels",
            required_info=["channels", "frequency"],
            questions={
                "channels": "Which communication channels should be used? (SMS/email/push/telegram, can select multiple)",
                "frequency": "How often should messages be sent? (immediate/daily/weekly)"
            }
        ),
        "scheduling": CampaignStep(
            task="Define campaign schedule",
            required_info=["start_date", "end_date"],
            questions={
                "start_date": "When should the campaign start?",
                "end_date": "When should the campaign end?"
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
    campaign_info = state["campaign_info"]
    current_step = campaign_info.steps[campaign_info.current_step]

    missing_info = [
        info for info in current_step.required_info
        if info not in current_step.collected_info
    ]
    print("CAMPAIGN_INFO_COLLECTED", campaign_info)
    print("CURRENT COLLECTED_INFO:", current_step.collected_info)

    collected_context = ""
    if current_step.collected_info:
        collected_context = "Information we've already collected:\n"
        for info_key, info_value in current_step.collected_info.items():
            collected_context += f"- {info_key}: {info_value}\n"

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
    messages = state["messages"]
    system_prompt = """You are a helpful assistant engaging in general conversation.
    Maintain a friendly and informative tone while providing relevant responses."""
    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
    return {
        "output": response.content,
        "messages": messages + [response]
    }

def route_based_on_action(state: TaskState):
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
workflow.add_node("task_identifier", task_identifier)
workflow.add_node("campaign_manager", campaign_manager)
workflow.add_node("campaign_planner", campaign_planner)
workflow.add_node("single_task_executor", single_task_executor)
workflow.add_node("general_conversation_agent", general_conversation_agent)
workflow.add_edge(START, "task_identifier")
workflow.add_edge("task_identifier", "campaign_manager")
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