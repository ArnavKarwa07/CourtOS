import re
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from courtos.config import Settings
from courtos.ai.gemini import GEMINI_MODEL_NAME, wait_for_gemini_slot
from courtos.db.adapter import DatabaseAdapter
from courtos.ai.state import AgentState

settings = Settings()

class OperatorAssistant:

    def __init__(self, db_adapter: DatabaseAdapter):
        self.db = db_adapter
        # Configure model (fallback to mock if key is missing for tests/simulation robustness)
        self.api_key = settings.gemini_api_key or "MOCK_KEY"
        self.model = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            google_api_key=self.api_key,
            max_retries=1
        )
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(AgentState)
        
        # Add Nodes
        builder.add_node("route_query", self.route_query)
        builder.add_node("query_db_secure", self.query_db_secure)
        builder.add_node("formulate_reply", self.formulate_reply)
        
        # Set entry point
        builder.set_entry_point("route_query")
        
        # Add conditional edges
        builder.add_conditional_edges(
            "route_query",
            self.decide_routing,
            {
                "query_db": "query_db_secure",
                "direct_reply": "formulate_reply"
            }
        )
        
        builder.add_edge("query_db_secure", "formulate_reply")
        builder.add_edge("formulate_reply", END)
        
        return builder.compile()

    async def route_query(self, state: AgentState) -> Dict[str, Any]:
        user_msg = state["messages"][-1].content
        
        # If API key is not configured, return immediately to direct reply
        if not settings.gemini_api_key:
            return {"context": {"route": "direct_reply"}}
            
        prompt = (
            "Analyze the operator query and decide if it requires searching or aggregating "
            "the database logs/incidents/telemetry or is a general query/help. "
            "Reply with exactly 'QUERY_DB' or 'DIRECT_REPLY'.\n"
            f"Query: {user_msg}"
        )
        try:
            await wait_for_gemini_slot()
            res = await self.model.ainvoke([HumanMessage(content=prompt)])
            route_decision = res.content.strip().upper()
            route = "query_db" if "QUERY_DB" in route_decision else "direct_reply"
        except Exception:
            route = "direct_reply"
            
        return {"context": {"route": route}}

    def decide_routing(self, state: AgentState) -> str:
        return state["context"].get("route", "direct_reply")

    async def query_db_secure(self, state: AgentState) -> Dict[str, Any]:
        user_msg = state["messages"][-1].content
        
        # Generate safe SQL select query based on db schema details
        prompt = (
            "You are a secure database translator. Write a single SQLite SELECT statement "
            "to answer the user query based on the following tables:\n"
            "1. telemetry_events (event_id, event_type, timestamp, source, payload)\n"
            "2. incidents (incident_id, severity, category, message, created_at, status, resolved_at)\n"
            "3. audit_log (log_id, action, actor, details, created_at)\n\n"
            "Rules:\n"
            "- Only write read-only SELECT statements.\n"
            "- Return EXACTLY the SQL query and nothing else. No markdown wrappers.\n"
            f"User query: {user_msg}"
        )
        
        try:
            await wait_for_gemini_slot()
            res = await self.model.ainvoke([HumanMessage(content=prompt)])
            sql = res.content.strip()
            # Clean markdown code block wraps if LLM added them
            sql = re.sub(r"```sql\s*|\s*```", "", sql)
            
            # Security sanitization
            upper_sql = sql.upper()
            forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE"]
            if any(term in upper_sql for term in forbidden) or not upper_sql.startswith("SELECT"):
                return {"queries": [sql], "context": {"db_error": "Security breach blocked: only SELECT queries allowed."}}

            # Run query against DB adapter
            rows = await self.db.execute_read(sql)
            return {"queries": [sql], "context": {"db_results": rows}}
            
        except Exception as e:
            return {"queries": [], "context": {"db_error": f"Failed to execute query: {str(e)}"}}

    async def formulate_reply(self, state: AgentState) -> Dict[str, Any]:
        user_msg = state["messages"][-1].content
        db_results = state["context"].get("db_results", None)
        db_err = state["context"].get("db_error", None)
        
        # Simple fallback for missing keys/testing
        if not settings.gemini_api_key:
            reply = (
                "Assistant: Gemini API key is not configured. Direct mock response. "
                f"You asked: '{user_msg}'"
            )
            return {"reply": reply}

        prompt = (
            "You are the CourtOS Operator AI Assistant. Answer the operator's question "
            "professionally using the provided database query results (if any).\n"
            f"Question: {user_msg}\n"
            f"Database Results: {db_results}\n"
            f"Database Error: {db_err}\n\n"
            "Formulate a helpful and concise reply."
        )
        try:
            await wait_for_gemini_slot()
            res = await self.model.ainvoke([HumanMessage(content=prompt)])
            reply = res.content.strip()
        except Exception:
            reply = f"Assistant: Direct fallback reply for question: '{user_msg}' (Gemini API query failed or was unauthorized)."
            
        return {"reply": reply}

    async def ask(self, query: str) -> str:
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "queries": [],
            "context": {},
            "commentary": "",
            "reply": ""
        }
        res = await self.workflow.ainvoke(initial_state)
        return res["reply"]
