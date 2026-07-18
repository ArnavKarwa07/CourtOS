import argparse
import asyncio
import uuid
from datetime import datetime, timezone
from courtos.config import Settings
from courtos.db.sqlite import SqliteAdapter
from courtos.db.postgres import PostgresAdapter
from courtos.models import TelemetryEvent
from courtos.models.enums import EventType

async def seed_data(count: int):
    settings = Settings()
    
    if settings.db_backend == "sqlite":
        db = SqliteAdapter(settings.db_url)
    else:
        db = PostgresAdapter(settings.db_url)
        
    await db.initialize()
    
    print(f"Seeding {count} events using {settings.db_backend} backend...")
    
    # Batch inserts
    for i in range(count):
        event_id = f"evt-seed-{i}-{uuid.uuid4()}"
        timestamp = datetime.now(timezone.utc)
        
        # Alternate event types
        if i % 3 == 0:
            payload = {
                "player_id": f"P{i%10}",
                "deceleration_g": float(i % 12),
                "velocity_ms": float(i % 20),
                "position_x": float(i * 1.5),
                "position_y": float(i * 0.8)
            }
            event_type = EventType.KINEMATIC
        elif i % 3 == 1:
            payload = {
                "channel": "telemetry",
                "bandwidth_mbps": 150.0 + (i * 2),
                "latency_ms": 1.5 + (i % 5)
            }
            event_type = EventType.NETWORK
        else:
            payload = {
                "play_state": "live" if i % 2 == 0 else "dead_ball",
                "game_clock": f"{12-(i%12):02d}:00",
                "period": max(1, min(4, i % 5))
            }
            event_type = EventType.GAME_STATE
            
        event = TelemetryEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            source="seed",
            payload=payload
        )
        
        await db.store_event(event)
        
    await db.write_audit("simulation_started", {"seed_count": count}, actor="system")
    await db.close()
    print("Seeding complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed CourtOS Database")
    parser.add_argument("--count", type=int, default=100, help="Number of telemetry events to generate")
    args = parser.parse_args()
    
    asyncio.run(seed_data(args.count))
