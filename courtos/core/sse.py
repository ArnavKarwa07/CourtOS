import asyncio
import json
from typing import List, AsyncGenerator, Optional

class SSEPublisher:
    """Service class.
    """

    def __init__(self):
        self._queues: List[asyncio.Queue] = []
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background keepalive/heartbeat ping loop."""
        self._heartbeat_task = asyncio.create_task(self._ping_loop())

    async def stop(self) -> None:
        """Cancel heartbeat task and close all queues."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Clear all queues
        for queue in list(self._queues):
            try:
                queue.put_nowait({"event": "close", "data": "Server shutting down"})
            except Exception:
                pass
        self._queues.clear()

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        """Subscribe to the SSE queue."""
        queue = asyncio.Queue(maxsize=100)
        self._queues.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            if queue in self._queues:
                self._queues.remove(queue)

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Broadcast event to all listeners."""
        json_data = data if isinstance(data, str) else json.dumps(data)
        event_payload = {
            "event": event_type,
            "data": json_data
        }
        for queue in list(self._queues):
            try:
                queue.put_nowait(event_payload)
            except (asyncio.QueueFull, Exception):
                # Remove stale connection queue
                if queue in self._queues:
                    self._queues.remove(queue)

    async def _ping_loop(self) -> None:
        """Heartbeat loop pushing keepalives every 15s to keep TCP alive."""
        try:
            while True:
                await asyncio.sleep(15.0)
                await self.broadcast("ping", {"heartbeat": True})
        except asyncio.CancelledError:
            pass
