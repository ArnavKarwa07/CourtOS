import json
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from courtos.config import Settings
from courtos.ai.gemini import GEMINI_MODEL_NAME, wait_for_gemini_slot
from courtos.ai.state import AgentState

settings = Settings()

class IncidentSummarizer:
    """Class description.\n"""

    def __init__(self):
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        self.api_key = settings.gemini_api_key or "MOCK_KEY"
        self.model = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            google_api_key=self.api_key,
            max_retries=1
        )
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        builder = StateGraph(AgentState)
        
        # Add Nodes
        builder.add_node("gather_incident_data", self.gather_incident_data)
        builder.add_node("generate_summary", self.generate_summary)
        
        # Connections
        builder.set_entry_point("gather_incident_data")
        builder.add_edge("gather_incident_data", "generate_summary")
        builder.add_edge("generate_summary", END)
        
        return builder.compile()

    async def gather_incident_data(self, state: AgentState) -> Dict[str, Any]:
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        # Context already contains raw incident object passed in initial_state
        return {"context": state.get("context", {})}

    async def generate_summary(self, state: AgentState) -> Dict[str, Any]:
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        incident = state["context"].get("incident", {})
        
        if not settings.gemini_api_key:
            # Mock fallback
            msg = (
                f"Incident resolved: {incident.get('message', 'No message')}. "
                f"Category: {incident.get('category', 'unknown')}. "
                "Generative AI summary not available (missing API key)."
            )
            return {"reply": msg}

        prompt = (
            "Summarize the following resolved incident for the court operations audit log. "
            "Write a concise paragraph detailing what happened, the severity level, and "
            "confirm it has been resolved by the operator.\n\n"
            f"Incident Details: {json.dumps(incident)}"
        )
        try:
            await wait_for_gemini_slot()
            res = await self.model.ainvoke([HumanMessage(content=prompt)])
            reply = res.content.strip()
        except Exception:
            reply = (
                f"Incident resolved: {incident.get('message', 'No message')}. "
                f"Category: {incident.get('category', 'unknown')}. "
                "AI summary fallback (Gemini API error occurred)."
            )
        return {"reply": reply}

    async def summarize(self, incident: Dict[str, Any]) -> str:
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        initial_state = {
            "messages": [],
            "queries": [],
            "context": {"incident": incident},
            "commentary": "",
            "reply": ""
        }
        res = await self.workflow.ainvoke(initial_state)
        return res["reply"]
