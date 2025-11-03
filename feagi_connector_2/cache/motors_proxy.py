import feagi_rust_py_libs as frpl
from .devices.motor_device_types import Percentage1D, Percentage4D, MiscData
from typing import Set, Dict

class MotorsProxy:

    # Mapping from device_full_name to cortical area prefix
    DEVICE_TO_CORTICAL_PREFIX: Dict[str, str] = {
        "rotary_motor_absolute_linear": "omot",
        "rotary_motor_absolute_fractional": "omot",
        "rotary_motor_incremental_linear": "omot",
        "rotary_motor_incremental_fractional": "omot",
        "positional_servo_absolute_linear": "oser",
        "positional_servo_absolute_fractional": "oser",
        "positional_servo_incremental_linear": "oser",
        "positional_servo_incremental_fractional": "oser",
        "gaze_absolute_linear": "ogaz",
        "gaze_incremental_linear": "ogaz",
        "miscellaneous_absolute": "omot",
        "miscellaneous_incremental": "omot",
    }

    def __init__(self, io_cache_ref: frpl.connector_core.caching.IOCache):
        self._registered_cortical_areas: Set[str] = set()
        
        self.rotary_motor_absolute_linear = Percentage1D(io_cache_ref, "rotary_motor_absolute_linear")
        self.rotary_motor_absolute_fractional = Percentage1D(io_cache_ref, "rotary_motor_absolute_fractional")
        self.rotary_motor_incremental_linear = Percentage1D(io_cache_ref, "rotary_motor_incremental_linear")
        self.rotary_motor_incremental_fractional = Percentage1D(io_cache_ref, "rotary_motor_incremental_fractional")
        self.positional_servo_absolute_linear = Percentage1D(io_cache_ref, "positional_servo_absolute_linear")
        self.positional_servo_absolute_fractional = Percentage1D(io_cache_ref, "positional_servo_absolute_fractional")
        self.positional_servo_incremental_linear = Percentage1D(io_cache_ref, "positional_servo_incremental_linear")
        self.positional_servo_incremental_fractional = Percentage1D(io_cache_ref, "positional_servo_incremental_fractional")

        self.gaze_absolute_linear = Percentage4D(io_cache_ref, "gaze_absolute_linear")
        self.gaze_incremental_linear = Percentage4D(io_cache_ref, "gaze_incremental_linear")
        self.miscellaneous_absolute = MiscData(io_cache_ref, "miscellaneous_absolute")
        self.miscellaneous_incremental = MiscData(io_cache_ref, "miscellaneous_incremental")
        
        # Set up registration callbacks for tracking
        self._setup_registration_tracking()
    
    def _setup_registration_tracking(self):
        """Set up callbacks to track motor device registrations."""
        devices = [
            ("rotary_motor_absolute_linear", self.rotary_motor_absolute_linear),
            ("rotary_motor_absolute_fractional", self.rotary_motor_absolute_fractional),
            ("rotary_motor_incremental_linear", self.rotary_motor_incremental_linear),
            ("rotary_motor_incremental_fractional", self.rotary_motor_incremental_fractional),
            ("positional_servo_absolute_linear", self.positional_servo_absolute_linear),
            ("positional_servo_absolute_fractional", self.positional_servo_absolute_fractional),
            ("positional_servo_incremental_linear", self.positional_servo_incremental_linear),
            ("positional_servo_incremental_fractional", self.positional_servo_incremental_fractional),
            ("gaze_absolute_linear", self.gaze_absolute_linear),
            ("gaze_incremental_linear", self.gaze_incremental_linear),
            ("miscellaneous_absolute", self.miscellaneous_absolute),
            ("miscellaneous_incremental", self.miscellaneous_incremental),
        ]
        
        for device_name, device_instance in devices:
            def make_callback(dev_name):
                def callback(cortical_group):
                    cortical_prefix = self.DEVICE_TO_CORTICAL_PREFIX.get(dev_name, "omot")
                    cortical_area = f"{cortical_prefix}{cortical_group:02d}"
                    self._registered_cortical_areas.add(cortical_area)
                return callback
            device_instance.set_registration_callback(make_callback(device_name))
    
    def get_registered_cortical_areas(self) -> list:
        """Return list of registered cortical areas (e.g., ['omot00', 'ogaz00'])."""
        return sorted(list(self._registered_cortical_areas))



