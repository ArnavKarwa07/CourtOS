import { useState, useCallback } from "react";
import type { TelemetryEvent } from "../types";

export function useTelemetryBuffer(initialEvents: TelemetryEvent[] = [], maxSize: number = 50) {
  const [telemetryFeed, setTelemetryFeed] = useState<TelemetryEvent[]>(() => initialEvents.slice(0, maxSize));

  const addEvent = useCallback((event: TelemetryEvent) => {
    setTelemetryFeed((prev) => [event, ...prev.slice(0, maxSize - 1)]);
  }, [maxSize]);

  const setEvents = useCallback((events: TelemetryEvent[]) => {
    setTelemetryFeed(events.slice(0, maxSize));
  }, [maxSize]);

  return { telemetryFeed, addEvent, setEvents };
}

