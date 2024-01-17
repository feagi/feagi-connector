"""
Copyright 2016-2022 The FEAGI Authors. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
==============================================================================
"""
# !/usr/bin/env python3

feagi_settings = {
    "feagi_url": None,  # gets updated
    "feagi_auth_url": None,  # composer for getting the Feagi URL link - First Priority
    "feagi_host": "127.0.0.1",  # feagi IP  - third priority
    "feagi_api_port": "8000",  # feagi Port - third priority
    "magic_link": ""
}

agent_settings = {
    "agent_data_port": "10004",
    "agent_id": "freenove",
    "agent_type": "embodiment",
    'TTL': 2,
    'last_message': 0,
    'compression': True
}

capabilities = {
    "servo": {
        "type": "opu",
        "disabled": False,
        'count': 2,
        'topic_identifier': '/S',
        'power_amount': 0.5

    },
    "motor": {
        "type": "opu",
        "disabled": False,
        "count": 4,
        "rolling_window_len": 2,
        "diameter_of_wheel": 0.065,
        "power_amount": 4094
    },
    "infrared": {
        "type": "ipu",
        "disabled": False,
        "count": 3,
        "cortical_mapping": "i__inf",
        'topic_identifier': 'IR'
    },
    "battery": {
        "type": "ipu",
        "disabled": False,
        "count": 4,
        "cortical_mapping": "i__bat",
        "capacity": 100,
        "depletion_per_burst": 0.01,
        "charge_increment": 0.1
    },
    "camera": {
        "type": "ipu",
        "disabled": False,
        "index": "00",
        "video_device_index": 0,
        "image": "",
        "video_loop": False,
        "mirror": False,
        # "enhancement": {1:80, 2:80, 4: 80}, # Example. Brightness, Constrast, Shadow
        # "gaze_control": {0: 25, 1: 55}, # Gaze shifts right
        # "pupil_control": {0: 25, 1: 55}, # Pupil shifts up
        "threshold_default": [100, 255, 130, 51] # min value, max value, min value, max value in
        # threshold setting. first and second is for regular webcam. Second is for vision blink OPU
    }
}

message_to_feagi = {"data": {}}
