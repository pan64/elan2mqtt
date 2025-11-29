from typing import Dict, Set, List
import logging
from device import Device
from event_bus import event_bus, EventType

logger = logging.getLogger(__name__)

class DeviceManager:
    def __init__(self):
        self.devices: List[Device] = []
        self.device_hash: Dict[str, Device] = {}
        self.device_addr_hash: Dict[str, Device] = {}
        self.active_devices: Set[str] = set()
        
    def add_device(self, device: Device) -> None:
        """Add device to collections"""
        self.devices.append(device)
        self.device_hash[device.id] = device
        self.device_addr_hash[str(device.data['device info']['address'])] = device
        self.active_devices.add(device.id)
        logger.info(f"Added device: {device.id}")
        
    def remove_device(self, device_id: str) -> None:
        """Remove device from all collections"""
        if device_id in self.device_hash:
            device = self.device_hash[device_id]
            self.devices.remove(device)
            del self.device_hash[device_id]
            addr = str(device.data['device info']['address'])
            if addr in self.device_addr_hash:
                del self.device_addr_hash[addr]
            self.active_devices.discard(device_id)
            logger.info(f"Removed device: {device_id}")
            
    def update_devices(self, current_devices: Dict[str, any]) -> None:
        """Update device collections based on current eLan state"""
        current_ids = set(d.get('id', '') for d in current_devices.values())
        
        # Remove devices no longer in eLan
        to_remove = self.active_devices - current_ids
        for device_id in to_remove:
            self.remove_device(device_id)
            
        # Add new devices
        for d in current_devices.values():
            device_id = d.get('id', '')
            if device_id not in self.device_hash:
                device = Device.create(d["url"])
                self.add_device(device)
                
    def clear_all(self) -> None:
        """Clear all device collections"""
        self.devices.clear()
        self.device_hash.clear()
        self.device_addr_hash.clear()
        self.active_devices.clear()
        logger.info("Cleared all devices")

device_manager = DeviceManager()