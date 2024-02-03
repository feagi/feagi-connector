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
import os

feagi_settings = {
    # "feagi_auth_url": os.environ.get('URL_MICROBIT', None),
    "feagi_url": None,
    "feagi_dns": None,
    "feagi_host": os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1"),
    "feagi_api_port": "8000",
}

agent_settings = {
    "agent_data_port": "100013",
    "agent_id": "raspberrypi-generic",
    "agent_type": "embodiment",
    'TTL': 2,
    'last_message': 0,
    'compression': True

}

capabilities = {
    "GPIO": {
        "port": {
            "2": 0,  # 0 is an output. 1 is an input
            "3": 0,
            "4": 0,
            "17": 0,
            "27": 0,
            "22": 0,
            "10": 0,
            "9": 0,
            "11": 0,
            "5": 0,
            "6": 0,
            "13": 0,
            "19": 0,
            "26": 0,
            "14": 1,
            "15": 1,
            "18": 1,
            "23": 1,
            "24": 1,
            "25": 1,
            "8": 1,
            "7": 1,
            "12": 1,
            "16": 1,
            "20": 1,
            "21": 1
        }
    }
}

message_to_feagi = {"data": {}}
