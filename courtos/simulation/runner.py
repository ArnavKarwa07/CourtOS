import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx
from courtos.ai.gemini import GEMINI_MIN_REQUEST_INTERVAL_SECONDS

logger = logging.getLogger("courtos.simulation")

class SimulationRunner:
    def __init__(self, port: int, interval_sec: float):
        self.port = port
        self.interval_sec = max(interval_sec, GEMINI_MIN_REQUEST_INTERVAL_SECONDS)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Simulation runner started", extra={"details": {"port": self.port, "interval_sec": self.interval_sec}})

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Simulation runner stopped")

    async def _loop(self) -> None:
        url = f"http://127.0.0.1:{self.port}/api/v1/telemetry"
        client = httpx.AsyncClient(headers={"X-Requested-With": "CourtOS-Client"})

        # Scripted phases: (play_state, duration_ticks, event_type)
        phases = [
            ("pre_game", 5, "network"),
            ("live", 15, "kinematic"),
            ("dead_ball", 5, "review"),
            ("live", 15, "kinematic"),
            ("timeout", 5, "review"),
            ("live", 15, "kinematic"),
            ("halftime", 10, "network"),
            ("live", 15, "kinematic"),
            ("post_game", 5, "network")
        ]

        phase_idx = 0
        ticks_in_phase = 0
        game_clock_sec = 720  # 12 minutes in seconds (720s)
        period = 1

        try:
            while self._running:
                play_state, duration, event_type = phases[phase_idx]
                
                # Check phase transitions
                if ticks_in_phase >= duration:
                    phase_idx = (phase_idx + 1) % len(phases)
                    play_state, duration, event_type = phases[phase_idx]
                    ticks_in_phase = 0
                    if play_state == "halftime":
                        period = min(4, period + 1)
                        game_clock_sec = 720

                # Decrement game clock during live play
                if play_state == "live" and game_clock_sec > 0:
                    game_clock_sec -= 5  # countdown 5 seconds per tick

                minutes = game_clock_sec // 60
                seconds = game_clock_sec % 60
                clock_str = f"{minutes:02d}:{seconds:02d}"

                event_id = f"evt-{uuid.uuid4()}"
                timestamp = datetime.now(timezone.utc).isoformat()
                
                # Prepare payload
                payload = {}
                if event_type == "network":
                    payload = {
                        "channel": "broadcast",
                        "bandwidth_mbps": 400.0 + (ticks_in_phase * 10),
                        "latency_ms": 2.5
                    }
                elif event_type == "review":
                    payload = {
                        "review_type": "foul_review",
                        "description": f"Foul review in period {period} at {clock_str}",
                        "requested_by": "referee"
                    }
                elif event_type == "kinematic":
                    # Generate warning breach at tick 7, critical breach at tick 12
                    decel = 2.0
                    velocity = 8.0
                    if ticks_in_phase == 7:
                        decel = 6.5  # Warn decel > 5.0
                    elif ticks_in_phase == 12:
                        decel = 10.5 # Crit decel > 9.0

                    payload = {
                        "player_id": "P24",
                        "deceleration_g": decel,
                        "velocity_ms": velocity,
                        "position_x": 10.0 + ticks_in_phase,
                        "position_y": 5.0 + ticks_in_phase
                    }

                # Push game state update first if phase changed or clock updated
                if ticks_in_phase == 0 or play_state == "live":
                    state_event = {
                        "event_id": f"evt-{uuid.uuid4()}",
                        "event_type": "game_state",
                        "timestamp": timestamp,
                        "source": "simulation",
                        "payload": {
                            "play_state": play_state,
                            "game_clock": clock_str,
                            "period": period
                        }
                    }
                    try:
                        await client.post(url, json=state_event)
                    except Exception as e:
                        logger.warning("Simulation runner state post failed", exc_info=e)

                # Push secondary event type
                event = {
                    "event_id": event_id,
                    "event_type": event_type,
                    "timestamp": timestamp,
                    "source": "simulation",
                    "payload": payload
                }

                try:
                    await client.post(url, json=event)
                except Exception as e:
                    logger.warning("Simulation runner event post failed", exc_info=e)

                ticks_in_phase += 1
                await asyncio.sleep(self.interval_sec)
        except asyncio.CancelledError:
            pass
        finally:
            await client.aclose()
