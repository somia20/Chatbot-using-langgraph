import json
from typing import Dict, Any, Optional
from groq import Groq

groq_client = Groq(api_key="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")

def call_groq_api(messages: list) -> str:
    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"Groq API error: {str(e)}")
    
def generate_completion_response(action: str, context: Dict[str, Any]) -> str:
    previous_messages = context.get('messages', [])
    conversation_history = json.dumps(previous_messages)
    
    messages = [
        {
            "role": "system", 
            "content": """Return only the completion message with no introductory phrases or meta-text. The message should:
            - Be exactly two lines
            - Start directly with the confirmation
            - Not include phrases like 'Here is' or 'This is'
            - Not repeat the message
            Format: Return just the quoted message with no other text."""
        },
        {
            "role": "user",
            "content": f"""Action: {action}
            Conversation history: {conversation_history}
            Create a completion message for the user."""
        }
    ]
    return call_groq_api(messages)


def generate_nlp_response(missing_field: str, context: Dict[str, Any]) -> str:
    previous_messages = context.get('messages', [])
    conversation_history = json.dumps(previous_messages)

    messages = [
        {
            "role": "system",
            "content": """You're an assistant helping create something.
            Ask for missing information conversationally. Keep it friendly and contextual."""
        },
        {
            "role": "user",
            "content": f"""Conversation history: {conversation_history}
            Ask for the user's {missing_field} naturally, referencing previous context."""
        }
    ]
    return call_groq_api(messages)

def extract_field_value(user_input: str, field: str, context: Dict[str, Any]) -> Optional[str]:
    messages = [
        {
            "role": "system",
            "content": """Extract specific information. Return ONLY the value or 'NOT_FOUND'."""
        },
        {
            "role": "user",
            "content": f"""Extract {field} from: "{user_input}"
            Context: {json.dumps(context.get('messages', []))}"""
        }
    ]
    extracted_value = call_groq_api(messages)
    return None if extracted_value == 'NOT_FOUND' else extracted_value.strip()


class ManagerAgent:
    def process_state(self, state_dict: Dict, state_id: str) -> Dict:
        current_state = state_dict[state_id].copy()

        # Find first False value in plan
        missing_fields = [field for field, value in current_state['plan'].items() if not value]

        if not missing_fields:
            # Generate dynamic completion message
            completion_response = generate_completion_response(
                current_state['action'], 
                current_state
            )
            current_state['output'] = "Complete"
            print("completion_response----------------->",completion_response)
            return {
                'updated_state': {state_id: current_state},
                'response': completion_response,
                'complete': True
            }

        # Generate response for first missing field
        response = generate_nlp_response(missing_fields[0], current_state)

        # Update state
        current_state['messages'].append({"role": "assistant", "content": response})
        current_state['output'] = f"Awaiting {missing_fields[0]}"

        return {
            'updated_state': {state_id: current_state},
            'response': response,
            'complete': False
        }

    def update_with_user_input(self, state_dict: Dict, user_input: str, state_id: str) -> Dict:
        current_state = state_dict[state_id].copy()

        # Add user message
        current_state['messages'].append({"role": "user", "content": user_input})

        # Process current missing field
        missing_fields = [field for field, value in current_state['plan'].items() if not value]
        if not missing_fields:
            return {
                'updated_state': {state_id: current_state},
                'response': "Already have all information",
                'complete': True
            }

        # Try to extract value
        current_field = missing_fields[0]
        extracted_value = extract_field_value(user_input, current_field, current_state)
        if extracted_value:
            current_state['plan'][current_field] = extracted_value

        # Pass both state_dict and state_id to process_state
        return self.process_state({state_id: current_state}, state_id)