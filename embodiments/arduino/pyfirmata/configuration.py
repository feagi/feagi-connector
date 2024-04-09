{
    "description": "generic_pyfirmata",
    "version": "v0.0.0",
    "feagi_settings": {
        "feagi_url": 'null',
        "feagi_dns": 'null',
        "feagi_host": "127.0.0.1",
        "feagi_api_port": 8000
    },
    "agent_settings": {
        "agent_data_port": 10007,
        "agent_id": "pyfirmata",
        "agent_type": "embodiment",
        "compression": 'true'
    },
    "capabilities": {
        "arduino": {
            "port": "/dev/ttyUSB0"
        },
        "motor": {
            "type": "opu",
            "disabled": False,
            "count": 24,  # 11 wheels but 11 for (forward/backward wheel) * 2 so 22
            "rolling_window_len": 1,
            "power_amount": 100
        }

    }
}

