import pytest
from unittest.mock import AsyncMock, MagicMock
from courtos.db.sqlite import SqliteAdapter
from courtos.ai.assistant import OperatorAssistant
from courtos.ai.summarizer import IncidentSummarizer
from courtos.ai.commentator import SportsCommentator

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
def mock_db():
    db = MagicMock(spec=SqliteAdapter)
    db.execute_read = AsyncMock(return_value=[{"event_id": "test_id", "message": "Telemetries"}])
    return db

@pytest.mark.anyio
async def test_operator_assistant_mock_flow(mock_db):
    assistant = OperatorAssistant(mock_db)
    
    # We test asking a basic question. Since gemini key is empty, it uses direct mock reply.
    reply = await assistant.ask("Hello, what is the status?")
    assert "Assistant:" in reply
    assert "Gemini API key is not configured" in reply
    assert "Hello, what is the status?" in reply

@pytest.mark.anyio
async def test_incident_summarizer_mock_flow():
    summarizer = IncidentSummarizer()
    incident = {
        "incident_id": "inc_abc",
        "severity": "critical",
        "category": "kinematic",
        "message": "Player decelerated too fast"
    }
    summary = await summarizer.summarize(incident)
    assert "Incident resolved:" in summary
    assert "inc_abc" in summary or "Player decelerated too fast" in summary

@pytest.mark.anyio
async def test_sports_commentator_mock_flow():
    commentator = SportsCommentator()
    event = {
        "event_id": "evt_123",
        "event_type": "kinematic_breach",
        "payload": {"game_clock": "05:42"}
    }
    commentary = await commentator.commentate(event)
    assert "Commentary:" in commentary
    assert "05:42" in commentary
