import asyncio
from typing import Dict, List, Callable, Any
from enum import Enum

class EventType(Enum):
    DEVICE_STATE_CHANGED = "device_state_changed"
    DEVICE_DISCOVERED = "device_discovered"
    MQTT_COMMAND_RECEIVED = "mqtt_command_received"
    ELAN_CONNECTED = "elan_connected"
    ELAN_DISCONNECTED = "elan_disconnected"

class EventBus:
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}
        
    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        
    async def publish(self, event_type: EventType, data: Any = None) -> None:
        if event_type in self._handlers:
            tasks = [handler(data) for handler in self._handlers[event_type]]
            await asyncio.gather(*tasks, return_exceptions=True)

event_bus = EventBus()