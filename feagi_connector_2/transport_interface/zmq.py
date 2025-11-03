from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any, Dict, Optional

import zmq
import zmq.asyncio

from ..callback import AsyncSignalWithParam


class FeagiZmqClient:
    """Manage FEAGI ZeroMQ sockets for registration, sensory and motor data.
    
    Uses 2-phase connection:
    1. Connect to registration endpoint only
    2. After registration, create data sockets using ports from response
    """

    def __init__(
        self,
        registration_address: str,
        *,
        context: Optional[zmq.asyncio.Context] = None,
    ) -> None:
        self._context = context or zmq.asyncio.Context.instance()

        self._registration_socket = self._context.socket(zmq.REQ)
        self._registration_socket.connect(registration_address)

        # Data sockets created AFTER registration
        self._sensory_socket: Optional[zmq.asyncio.Socket] = None
        self._motor_socket: Optional[zmq.asyncio.Socket] = None

        self.motor_signal: AsyncSignalWithParam[bytes] = AsyncSignalWithParam()
        self._motor_listener: Optional[asyncio.Task[None]] = None

    async def send_registration(self, feagi_host: str, camera_resolution_xyc: (int, int, int), sensory_port: int) -> dict:
        """Send registration and create data sockets from response.
        
        Args:
            feagi_host: FEAGI host address (e.g., "tcp://localhost")
            camera_resolution_xyc: Camera resolution (width, height, channels)
            sensory_port: Sensory data port from config
        
        Returns:
            Registration response dict
        """

        payload = {
            "method": "POST",
            "path": "/v1/agent/register",
            "body": {
                "agent_id": "autonomous_robot",
                "agent_type": "both",
                "capabilities": {
                    "vision": {
                        "modality": "camera",
                        "dimensions": [camera_resolution_xyc[0], camera_resolution_xyc[1]],
                        "channels": camera_resolution_xyc[2],
                        "target_cortical_area": "iic400"
                    },
                    "motor": {
                        "modality": "wheel_motors",
                        "output_count": 2,
                        "source_cortical_areas": ["omot00"]
                    }
                }
            }
        }

        message = json.dumps(payload).encode("utf-8")
        await self._registration_socket.send(message)
        response: bytes = await self._registration_socket.recv()
        response_str: str = response.decode("utf-8")
        data_dict = json.loads(response_str)
        print(data_dict)
        
        # Phase 2: Create data sockets using ports from registration response
        zmq_ports = data_dict.get('body', {}).get('zmq_ports', {})
        motor_port = zmq_ports.get('motor', 5564)  # @architecture:acceptable - emergency fallback
        
        # Create sensory socket (PUSH to FEAGI)
        sensory_address = f"{feagi_host}:{sensory_port}"
        self._sensory_socket = self._context.socket(zmq.PUSH)
        self._sensory_socket.connect(sensory_address)
        print(f"[ZMQ-CLIENT] Connected to sensory at {sensory_address}")
        
        # Create motor socket (SUB from FEAGI's PUB)
        motor_address = f"{feagi_host}:{motor_port}"
        self._motor_socket = self._context.socket(zmq.SUB)
        self._motor_socket.connect(motor_address)
        self._motor_socket.setsockopt(zmq.SUBSCRIBE, b"")
        print(f"[ZMQ-CLIENT] Connected to motor at {motor_address}")
        
        return data_dict

    async def push_sensory_data(self, data: bytes) -> None:
        """Push sensory byte data towards FEAGI."""
        if self._sensory_socket is None:
            raise RuntimeError("Sensory socket not connected. Call send_registration first.")
        await self._sensory_socket.send(data)

    def start_motor_listener(self) -> None:
        """Start the background task that relays motor bytes to registered callbacks."""

        if self._motor_listener is None or self._motor_listener.done():
            loop = asyncio.get_running_loop()
            self._motor_listener = loop.create_task(self._motor_loop())

    async def _motor_loop(self) -> None:
        """Background task that receives motor data from FEAGI and emits it via signal."""
        if self._motor_socket is None:
            print(f"[ZMQ-CLIENT] ❌ Motor socket not connected. Call send_registration first.")
            return
        print(f"[ZMQ-CLIENT] 🎮 Motor listener loop started (waiting for data from FEAGI)")
        while True:
            data = await self._motor_socket.recv()
            print(f"[ZMQ-CLIENT] 🎮 RECEIVED motor data from FEAGI: {len(data)} bytes")
            await self.motor_signal.emit(data)

    async def close(self) -> None:
        """Close sockets and stop the motor listener."""

        if self._motor_listener is not None:
            self._motor_listener.cancel()
            with suppress(asyncio.CancelledError):
                await self._motor_listener

        self._registration_socket.close(linger=0)
        if self._sensory_socket is not None:
            self._sensory_socket.close(linger=0)
        if self._motor_socket is not None:
            self._motor_socket.close(linger=0)


