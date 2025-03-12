import operator
from typing import List, Optional, Dict, Any, Annotated, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq  # Change to your preferred LLM
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver

# Campaign structures
class CampaignStep(BaseModel):
    """Represents a single step in the campaign creation process"""
    task: str
    required_info: List[str]
    collected_info: Dict[str, Any] = Field(default_factory=dict)
    validation_rules: Dict[str, str]
    questions: Dict[str, str]  # Maps required_info to specific questions
    last_question: Optional[str] = None  # Tracks the last question asked
    expected_input: Optional[str] = None  # Tracks what input we're expecting
    status: str = "pending"  # pending/in_progress/completed
    output: Optional[str] = None


class CampaignInfo(BaseModel):
    """Tracks overall campaign information and progress"""
    steps: Dict[str, CampaignStep]
    current_step: str
    stage: str = "planning"  # planning/collection/validation/complete


# State definitions
class OverallState(MessagesState):
    user_input:  Annotated[str, lambda x, y: y]
    campaign_info: Annotated[CampaignInfo, lambda old, new: new]
    segment_results: Annotated[list, operator.add]
    action_results: Annotated[list, operator.add]
    channel_results: Annotated[list, operator.add]
    schedule_results: Annotated[list, operator.add]
    action:Annotated[str, lambda x, y: y]
    pending_steps:Annotated[list, operator.add]
    follow_up_message: Optional[str] = None
    stage :Annotated[str, operator.add]


class ExtractState(TypedDict):
    user_input: str


class TaskIdentification(BaseModel):
    task_type: Literal["general_convo", "campaign_convo", "other_services"]
    description: str

class ActionData(BaseModel):
    action_type: str = Field(description="The type of action (bonus/discount) or empty string if none found")
    reward_value: str = Field(description="The value amount or empty string if none found")
    duration_days: str = Field(description="The duration in days or empty string if none found")



class ChannelData(BaseModel):
    channels: str = Field(description="The communication channels or empty string if none found")
    frequency: str = Field(description="The frequency or empty string if none found")


class ScheduleData(BaseModel):
    start_date: str = Field(description="The start date or empty string if none found")
    end_date: str = Field(description="The end date or empty string if none found")



class SegmentExtraction(BaseModel):
    segment_condition: str = Field(description="The extracted segment condition or empty string if none found")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")

class ActionExtraction(BaseModel):
    action_type: str = Field(description="The type of action (bonus/discount) or empty string if none found")
    reward_value: str = Field(description="The value amount or empty string if none found")
    duration_days: str = Field(description="The duration in days or empty string if none found")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")

class ChannelExtraction(BaseModel):
    channels: str = Field(description="The communication channels or empty string if none found")
    frequency: str = Field(description="The frequency or empty string if none found")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")

class ScheduleExtraction(BaseModel):
    start_date: str = Field(description="The start date or empty string if none found")
    end_date: str = Field(description="The end date or empty string if none found")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")


class UpdateIntent(BaseModel):
    """Model for detecting update intent in user messages"""
    update_type: Literal["segment", "action", "channel", "schedule", "none"] = Field(
        description="The aspect of the campaign the user wants to update")
    confidence: float = Field(
        description="Confidence level between 0 and 1 that this is an update request")