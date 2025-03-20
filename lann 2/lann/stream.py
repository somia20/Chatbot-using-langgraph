import streamlit as st
from main import graph, initialize_campaign_info
import uuid
from typing import List, Dict, Any
import json

# Set page configuration
st.set_page_config(
    page_title="Campaign Management System",
    page_icon="📊",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
.user-message {
    background-color: #e6f7ff;
    padding: 10px;
    border-radius: 10px;
    margin-bottom: 10px;
    display: flex;
    align-items: flex-start;
}
.bot-message {
    background-color: #f0f0f0;
    padding: 10px;
    border-radius: 10px;
    margin-bottom: 10px;
    display: flex;
    align-items: flex-start;
}
.message-content {
    margin-left: 10px;
    flex-grow: 1;
}
.user-icon {
    background-color: #1f77b4;
    color: white;
    border-radius: 50%;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
}
.bot-icon {
    background-color: #2ca02c;
    color: white;
    border-radius: 50%;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
}
.app-header {
    text-align: center;
    margin-bottom: 20px;
}
.debug-info {
    font-family: monospace;
    font-size: 12px;
    white-space: pre-wrap;
    overflow-x: auto;
}
</style>
""", unsafe_allow_html=True)

# App header
st.markdown("<div class='app-header'><h1>Campaign Management System</h1></div>", unsafe_allow_html=True)

# Initialize session state variables
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_state" not in st.session_state:
    st.session_state.last_state = None

if "first_message_processed" not in st.session_state:
    st.session_state.first_message_processed = False

if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = False


# Function to display the chat history
def display_chat_history():
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"""
            <div class='user-message'>
                <div class='user-icon'>U</div>
                <div class='message-content'>{message['content']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Clean any closing div tags that might appear in the content
            content = message["content"].replace("</div>", "").replace(
                "Please confirm if these details are correct or let me know what you'd like to change.", "")
            st.markdown(f"""
            <div class='bot-message'>
                <div class='bot-icon'>B</div>
                <div class='message-content'>{content}</div>
            </div>
            """, unsafe_allow_html=True)


# Function to process user input and get response
def process_message(user_input: str) -> str:
    # Set up initial state
    if not st.session_state.first_message_processed:
        # Initialize campaign for the first message
        campaign_info = initialize_campaign_info()

        initial_state = {
            "user_input": user_input,
            "campaign_info": campaign_info,
            "segment_results": [],
            "action_results": [],
            "channel_results": [],
            "schedule_results": []
        }
        st.session_state.first_message_processed = True
    else:
        # For subsequent messages, use minimal state and rely on memory
        initial_state = {
            "user_input": user_input,
            "segment_results": [],
            "action_results": [],
            "channel_results": [],
            "schedule_results": []
        }

    # Configure thread for memory
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    # Run the graph
    with st.spinner("Processing..."):
        if st.session_state.debug_mode:
            st.write(f"Debug - Processing message with thread ID: {st.session_state.thread_id}")
        result = graph.invoke(initial_state, config)

    # Save the result state for debugging
    st.session_state.last_state = result

    # Get the last message from the result
    if "messages" in result and len(result["messages"]) > 0:
        content = result["messages"][-1].content
        # Clean any problematic strings
        content = content.replace(
            "Please confirm if these details are correct or let me know what you'd like to change.", "")
        return content
    else:
        return "I couldn't process your request. Please try again."


# Create a single column layout
col1 = st.container()

# Small footer area for controls
with st.container():
    col_btn, col_debug = st.columns([1, 5])

    with col_btn:
        # Add a button to reset the conversation
        if st.button("Start New Campaign"):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.first_message_processed = False
            st.session_state.last_state = None
            st.rerun()

    with col_debug:
        # Add debugging toggle
        debug_toggle = st.checkbox("Show Debug Info", value=st.session_state.debug_mode)
        if debug_toggle != st.session_state.debug_mode:
            st.session_state.debug_mode = debug_toggle
            st.rerun()

with col1:
    # Display chat history
    display_chat_history()

    # Create the input box for user messages
    user_input = st.text_input("Type your message here:", key="input_field")
    col_send, col_clear = st.columns([1, 5])

    with col_send:
        send_button = st.button("Send")

    # Process the message when the user submits
    if send_button and user_input:
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Get bot response
        bot_response = process_message(user_input)

        # Add bot response to history
        st.session_state.messages.append({"role": "assistant", "content": bot_response})

        # Rerun to update the UI
        st.rerun()

    # Debug information if enabled
    if st.session_state.debug_mode and st.session_state.last_state:
        st.subheader("Debug Information")
        st.write(f"Thread ID: {st.session_state.thread_id}")
        st.write(f"First message processed: {st.session_state.first_message_processed}")

        # Check campaign info
        if "campaign_info" in st.session_state.last_state:
            campaign_info = st.session_state.last_state["campaign_info"]
            st.write("Campaign Stage:", campaign_info.stage)
            st.write("Current Step:", campaign_info.current_step)

            # Show status of each step
            st.write("Step Status:")
            for step_name, step in campaign_info.steps.items():
                st.write(f"- {step_name}: {step.status}")
                if step.collected_info:
                    st.write(f"  Collected info: {json.dumps(step.collected_info, indent=2)}")

            # Show other details from the state
            if "campaign_manager_state" in st.session_state.last_state:
                manager_state = st.session_state.last_state["campaign_manager_state"]
                st.write("Campaign Manager Stage:", manager_state.stage)

# Add a footer
st.markdown("---")
st.markdown("<div style='text-align: center'>Campaign Management System | Powered by LangGraph</div>",
            unsafe_allow_html=True)