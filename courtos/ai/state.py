from typing import TypedDict, List, Annotated, Dict, Any
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):

    messages: Annotated[List[BaseMessage], operator.add]
    queries: List[str]
    context: Dict[str, Any]
    commentary: str
    reply: str
