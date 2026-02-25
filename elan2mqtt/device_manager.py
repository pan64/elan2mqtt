from typing import Dict, Set, List, Any
import logging
from device import Device


logger = logging.getLogger(__name__)


class DeviceManager:
    def __init__(self):
        self.devices: List[Device] = []
        self.device_hash: Dict[str, Device] = {}
        self.device_addr_hash: Dict[str, Device] = {}
        self.active_devices: Set[str] = set()

    def add_device(self, device: Device) -> None:
        """Add device to collections"""
        try:
            self.devices.append(device)
            self.device_hash[device.id] = device
            self.device_addr_hash[str(device.data['device info']['address'])] = device
            self.active_devices.add(device.id)
            logger.info(f"Added device: {device.id}")
        except (KeyError, TypeError) as e:
            logger.error("Invalid device data structure: {}".format(str(e)))
            raise
        except Exception as e:
            logger.error("Failed to add device: {}".format(str(e)))
            raise

    def remove_device(self, device_id: str) -> None:
        """Remove device from all collections"""
        try:
            if device_id in self.device_hash:
                device = self.device_hash[device_id]
                self.devices.remove(device)
                del self.device_hash[device_id]
                addr = str(device.data['device info']['address'])
                if addr in self.device_addr_hash:
                    del self.device_addr_hash[addr]
                self.active_devices.discard(device_id)
                logger.info(f"Removed device: {device_id}")
        except (KeyError, ValueError) as e:
            logger.error("Error removing device {}: {}".format(device_id, str(e)))
        except Exception as e:
            logger.error("Unexpected error removing device {}: {}".format(device_id, str(e)))

    async def update_devices(self, current_devices: Dict[str, Any]) -> None:
        """Update device collections based on current eLan state"""
        try:
            current_ids = set(d.get('id', '') for d in current_devices.values())

            # Remove devices no longer in eLan
            to_remove = self.active_devices - current_ids
            for device_id in to_remove:
                self.remove_device(device_id)

            # Add new devices
            for d in current_devices.values():
                device_id = d.get('id', '')
                if device_id not in self.device_hash:
                    try:
                        device = await Device.create(d["url"])
                        self.add_device(device)
                    except Exception as e:
                        logger.error("Failed to create device from {}: {}".format(d.get("url", "unknown"), str(e)))
        except (KeyError, TypeError) as e:
            logger.error("Invalid device list format: {}".format(str(e)))
            raise
        except Exception as e:
            logger.error("Error updating devices: {}".format(str(e)))
            raise

    def clear_all(self) -> None:
        """Clear all device collections"""
        self.devices.clear()
        self.device_hash.clear()
        self.device_addr_hash.clear()
        self.active_devices.clear()
        logger.info("Cleared all devices")


device_manager = DeviceManager()
