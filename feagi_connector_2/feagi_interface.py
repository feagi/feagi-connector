from typing import Callable, Awaitable, TypeVar, Generic
from feagi_connector_2.callback import AsyncSignal
from feagi_connector_2.transport_interface.zmq import FeagiZmqClient

class FeagiInterface:

    def __init__(self):
        self._signal_connected_and_registered: AsyncSignal = AsyncSignal()
        self._signal_connection_failed: AsyncSignal = AsyncSignal() # TODO reason?
        self._signal_connection_ended: AsyncSignal = AsyncSignal()

        self._transport = None

    def register_callback_for_connection_and_registration_success(self, callback: Callable[[], Awaitable[None]]) -> None:
        self._signal_connected_and_registered.register(callback)

    def register_callback_for_connection_failure(self, callback: Callable[[], Awaitable[None]]) -> None:
        self._signal_connection_failed.register(callback)

    def register_callback_for_connection_end_success(self, callback: Callable[[], Awaitable[None]]) -> None:
        self._signal_connection_ended.register(callback)

    async def connect_to_neurorobotics_studio(self) -> bool:
        raise NotImplementedError

    async def connect_via_zmq(self, feagi_host_address: str, camera_resolution_xyc: (int, int, int), registration_port: int = 30001, sensory_port: int = 5558, heartbeat_interval: float = 5.0) -> dict:
        """Connect to FEAGI via ZMQ using 2-phase connection.
        
        Phase 1: Connect to registration endpoint (well-known port)
        Phase 2: Create data sockets using ports from registration response
        
        Args:
            feagi_host_address: FEAGI host (e.g., "tcp://localhost")
            camera_resolution_xyc: Camera resolution (width, height, channels)
            registration_port: Registration endpoint port (from FEAGI config)
            sensory_port: Sensory data port (from FEAGI config)
            heartbeat_interval: Heartbeat interval in seconds
        
        Returns:
            Registration response dict with actual motor/viz ports
        """

        registration_endpoint: str = feagi_host_address + ":" + str(registration_port)

        # Phase 1: Connect to registration only
        self._transport = FeagiZmqClient(registration_endpoint)
        
        # Phase 2: Register and get actual ports, then create data sockets
        response = await self._transport.send_registration(feagi_host_address, camera_resolution_xyc, sensory_port)
        return response