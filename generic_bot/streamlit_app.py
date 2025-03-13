import streamlit as st
import json
import asyncio
from classification import process_message

def init_session_state():
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'conversation_id' not in st.session_state:
        st.session_state.conversation_id = None

async def process_user_message(user_input: str):
    """Process user message and get response from the chatbot"""
    try:
        response = await process_message(user_input)
        
        # If response is a JSON string, parse it
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            pass
            
        # Extract the actual message content if it's in a dictionary
        if isinstance(response, dict) and 'message' in response:
            response = response['message']
            
        return response
    except Exception as e:
        st.error(f"Error processing message: {str(e)}")
        return "I apologize, but I encountered an error processing your message."

def main():
    st.title("AI Chatbot")
    
    # Initialize session state
    init_session_state()
    
    # Chat interface
    st.markdown("### Chat")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if user_input := st.chat_input("Type your message here..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        # Show typing indicator while processing
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Process message and get response
                response = asyncio.run(process_user_message(user_input))
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.markdown(response)
    
    # Clear chat button
    if st.sidebar.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

if __name__ == "__main__":
    st.set_page_config(
        page_title="AI Chatbot",
        page_icon="💬",
        layout="wide"
    )
    main()