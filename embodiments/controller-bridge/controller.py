#!/usr/bin/env python
"""
Copyright 2016-2024 The FEAGI Authors. All Rights Reserved.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
===============================================================================
"""

import asyncio
import threading
from time import sleep
import time
from datetime import datetime
import traceback

import numpy as np
import websockets
import requests
import lz4.frame
import pickle

from configuration import *
from collections import deque
from feagi_connector import retina
from version import __version__
from feagi_connector import feagi_interface as feagi
from feagi_connector import pns_gateway as pns

ws = deque()
ws_operation = deque()


async def echo(websocket):
    """
    The function echoes the data it receives from other connected websockets
    and sends the data from FEAGI to the connected websockets.
    """
    global message_to_feagi
    async for message in websocket:
        if not ws_operation:
            ws_operation.append(websocket)
        else:
            ws_operation[0] = websocket
        message_to_feagi = pickle.loads(message)


if __name__ == "__main__":
    while True:
        feagi_flag = False
        print("Waiting on FEAGI...")
        while not feagi_flag:
            feagi_flag = feagi.is_FEAGI_reachable(os.environ.get('FEAGI_HOST_INTERNAL',
                                                                 "127.0.0.1"),
                                                  int(os.environ.get('FEAGI_OPU_PORT', "3000")))
            sleep(2)
        print("DONE")
        previous_data_frame = {}
        runtime_data = {"cortical_data": {}, "current_burst_id": None,
                        "stimulation_period": 0.01, "feagi_state": None,
                        "feagi_network": None}

        # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
            feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                                   __version__)
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        pns.start_websocket_in_threads(echo,
                                       agent_settings["godot_websocket_ip"],
                                       agent_settings['godot_websocket_port'],
                                       ws_operation, ws,
                                       feagi_settings)
        threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
        while True:
            try:
                message_from_feagi = pns.message_from_feagi
                if message_from_feagi:
                    ws.append(pickle.dumps(message_from_feagi))
                    feagi_settings['feagi_burst_speed'] = message_from_feagi['burst_frequency']
                sleep(feagi_settings['feagi_burst_speed'])  # bottleneck
                pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings)
                message_to_feagi.clear()
            except Exception as e:
                # pass
                print("ERROR! : ", e)
                traceback.print_exc()
                break
