import json
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from courtos.config import Settings
from courtos.ai.gemini import GEMINI_MODEL_NAME, wait_for_gemini_slot
from courtos.ai.state import AgentState

settings = Settings()

class SportsCommentator:
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
        builder.add_node("analyze_event", self.analyze_event)
        builder.add_node("generate_commentary", self.generate_commentary)

        # Connections
        builder.set_entry_point("analyze_event")
        builder.add_edge("analyze_event", "generate_commentary")
        builder.add_edge("generate_commentary", END)

        return builder.compile()

    async def analyze_event(self, state: AgentState) -> Dict[str, Any]:
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        # Context already contains event details
        return {"context": state.get("context", {})}

    async def generate_commentary(self, state: AgentState) -> Dict[str, Any]:
        """Method description.

        Args:
        *args: Arguments.
        **kwargs: Keyword arguments.

        Returns:
        Any: Return value.

        Raises:
        Exception: If an error occurs.

        """
        event_data = state["context"].get("event", {})

        payload = event_data.get("payload", {}) or {}
        event_type = str(event_data.get("event_type", "update"))

        game_clock = payload.get("game_clock") or "00:00"
        period = payload.get("period") or None
        play_state = payload.get("play_state") or None
        player_id = payload.get("player_id") or None

        incidents_hint = (
            "This event may have triggered player-safety or foul-review style incidents "
            "based on tracking-derived thresholds."
        )

        if not settings.gemini_api_key:
            # Mock fallback (basketball-focused + injury/tracking integration flavored)
            if event_type == "game_state":
                return {
                    "commentary": (
                        f"Play status update: {str(play_state).replace('_', ' ').upper()} — "
                        f"{game_clock} left in Q{period if period else '1'}. "
                        f"Tracking systems are ready for real-time safety and foul-review cues."
                    )
                }
            if event_type == "kinematic":
                return {
                    "commentary": (
                        f"Tracking telemetry spikes for player {player_id or 'unknown'}: "
                        f"movement intensity suggests a possible safety check at {game_clock}. "
                        f"Like the NBA, we use motion tracking to flag situations for review."
                    )
                }
            return {
                "commentary": (
                    f"Commentary: Live update ({event_type}) at {game_clock}. "
                    f"Machine tracking continues feeding the venue dashboard for instant review signals."
                )
            }

        prompt = (
            "You are CourtOS, a basketball arena live commentator for a scoreboard/ops dashboard.\n"
            "Write EXACTLY ONE short, punchy sentence (max ~28 words).\n\n"
            "The sentence MUST:\n"
            "1) Reference basketball game context if available: play_state, game_clock, period.\n"
            "2) If the event looks like player tracking (kinematic), mention motion/tracking-derived safety cues and an injury check possibility.\n"
            "3) If the event looks like a review/foul review, mention that it’s a tracking-informed foul-review workflow.\n"
            "4) Keep it realistic: no generic 'simulated' language. Sound like it’s happening right now.\n"
            "5) Maintain tempo like live play-by-play.\n\n"
            f"Event Data (JSON): {json.dumps(event_data)}\n\n"
            f"Incidents Hint: {incidents_hint}"
        )
        try:
            await wait_for_gemini_slot()
            res = await self.model.ainvoke([HumanMessage(content=prompt)])
            reply = res.content.strip().replace("\n", " ")
        except Exception:
            # Deterministic fallback if model fails
            if event_type == "game_state":
                reply = (
                    f"Play status: {str(play_state).replace('_', ' ').upper()} — {game_clock} left in Q{period if period else '1'}. "
                    f"Tracking sensors are standing by for safety and review signals."
                )
            elif event_type == "kinematic":
                reply = (
                    f"Tracking alert for player {player_id or 'unknown'} at {game_clock}: motion intensity suggests a possible injury check—"
                    f"tracking technology helps flag foul-review moments."
                )
            else:
                reply = f"Live basketball update at {game_clock}: tracking telemetry continues driving instant review cues."
        return {"commentary": reply}

    async def commentate(self, event: Dict[str, Any]) -> str:
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
            "context": {"event": event},
            "commentary": "",
            "reply": ""
        }
        res = await self.workflow.ainvoke(initial_state)
        return res["commentary"]
