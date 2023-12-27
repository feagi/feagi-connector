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
    # "feagi_auth_url": "http://127.0.0.1:9000/v1/k8/feagi_settings/auth_token",
    "feagi_url": None,
    "feagi_dns": None,
    "feagi_host": "127.0.0.1",
    "feagi_api_port": "8000",
}

agent_settings = {
    "agent_data_port": "10002",
    "agent_id": "tello_drone",
    "agent_type": "embodiment",
    'TTL': 2,
    'last_message': 0,
    'compression': True
}

capabilities = {
    "camera": {
        "type": "ipu",
        "disabled": False,
        "index": "00",
        "threshold_default": [50, 255, 130, 51],  # min #1, max #1, min #2, max #2,
        "threshold_type": {},  # simple thresholding types. see the retina.threshold_detect function
        "threshold_name": 0,  # Binary_threshold as a default
        "mirror": True,  # flip the image?
        "blink": [],  # Blink to see the "invert" image. Needs `o_blnk`
        "gaze_control": {0: 1, 1: 99}, # Controlled by o__gaz OPU
        "pupil_control": {0: 1, 1: 99}, # Controlled by o__pup
        "vision_range": [1, 99],  # min, max
        "size_list": [],  # To get the size in real time based on genome's change/update
        "enhancement": {}  # Enable ov_enh OPU on inside the genome
    },
    "battery": {
        "type": "ipu",
        "disabled": False,
        "count": 4,
        "refresh_rate": 1,
        "cortical_mapping": "i__bat",
        "capacity": 100,
        "depletion_per_burst": 0.01,
        "charge_increment": 0.1
    },
    "gyro": {
        "resolution": 20,
        "range": [-180, 180]  # -180 to 180 degree
    },
    "acc": {
        "resolution": 20,
        "range": [-1200, 1200]
    },
    "misc": {
        "type": "opu"
    },
    "navigation": {
        "type": "opu"
    }
}

message_to_feagi = {"data": {}}
