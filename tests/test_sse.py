import asyncio
import pytest
from courtos.core.sse import SSEPublisher

@pytest.mark.asyncio
async def test_sse_publisher_lifecycle():
    publisher = SSEPublisher()
    
    # Test subscribe generator
    subscription = publisher.subscribe()
    
    sub_task = asyncio.create_task(subscription.__anext__())
    await asyncio.sleep(0.01)

    # Broadcast custom event directly without ping loop
    await publisher.broadcast("test_event", {"message": "hello"})

    received = await sub_task
    
    assert received["event"] == "test_event"
    assert "hello" in received["data"]

    # Stop publisher
    await publisher.stop()
    assert len(publisher._queues) == 0
