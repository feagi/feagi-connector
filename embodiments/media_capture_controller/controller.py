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

import os
import time
import json
import asyncio
import requests
import traceback
import lz4.frame
import threading
import websockets
import numpy as np
from time import sleep
from collections import deque
from datetime import datetime
from version import __version__
from feagi_connector import retina
from feagi_connector import sensors
from feagi_connector import pns_gateway as pns
from feagi_connector import feagi_interface as feagi

rgb_array = {}
ws = deque()
ws_operation = deque()
webcam_size = {'size': []}
connected_agents = dict()  # Initalize
connected_agents['0'] = False  # By default, it is not connected by client's websocket


async def bridge_to_godot(runtime_data):
    while True:
        if ws:
            try:
                if ws_operation:
                    if len(ws) > 0:
                        if len(ws) > 2:
                            stored_value = ws.pop()
                            ws.clear()
                            ws.append(stored_value)
                    await ws_operation[0].send(str(ws[0]))
                    ws.pop()
                sleep(runtime_data["stimulation_period"])
            except Exception as error:
                print("error in websocket sender: ", error)
                traceback.print_exc()
                sleep(0.001)
        else:
            sleep(0.001)


def bridge_operation(runtime_data):
    asyncio.run(bridge_to_godot(runtime_data))


def utc_time():
    current_time = datetime.utcnow()
    return current_time


async def echo(websocket):
    """
    The function echoes the data it receives from other connected websockets
    and sends the data from FEAGI to the connected websockets.
    """
    global connected_agents
    ws.append({"newRefreshRate": 60})
    async for message in websocket:
        connected_agents['0'] = True  # Since this section gets data from client, its marked as true
        if not ws_operation:
            ws_operation.append(websocket)
        else:
            ws_operation[0] = websocket
        test = message
        rgb_array['current'] = list(lz4.frame.decompress(test))
        webcam_size['size'] = []
    connected_agents['0'] = False  # Once client disconnects, mark it as false


async def main():
    """
    The main function handles the websocket and spins the asyncio to run the echo function
    infinitely until it exits. Once it exits, the function will resume to the next new websocket.
    """
    async with websockets.serve(echo, agent_settings["godot_websocket_ip"],
                                agent_settings['godot_websocket_port'], max_size=None,
                                max_queue=None, write_limit=None, compression=None):
        await asyncio.Future()  # run forever


def websocket_operation():
    """
    WebSocket initialized to call the echo function using asyncio.
    """
    asyncio.run(main())


if __name__ == "__main__":
    # NEW JSON UPDATE
    f = open('configuration.json')
    configuration = json.load(f)
    feagi_settings = configuration["feagi_settings"]
    agent_settings = configuration['agent_settings']
    capabilities = configuration['capabilities']
    feagi_settings['feagi_host'] = os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1")
    feagi_settings['feagi_api_port'] = os.environ.get('FEAGI_API_PORT', "8000")
    agent_settings['godot_websocket_port'] = os.environ.get('WS_WEBCAM_PORT', "9051")
    # agent_settings['godot_websocket_ip'] = os.environ.get('WS_MICROBIT_PORT', "9052")
    f.close()
    message_to_feagi = {"data": {}}
    # END JSON UPDATE
    runtime_data = {"cortical_data": {}, "current_burst_id": None,
                    "stimulation_period": 0.01, "feagi_state": None,
                    "feagi_network": None}
    rgb = {}
    CHECKPOINT_TOTAL = 5
    rgb['camera'] = {}
    rgb_array['current'] = {}
    camera_data = {"vision": {}}
    threading.Thread(target=websocket_operation, daemon=True).start()
    threading.Thread(target=bridge_operation, args=(runtime_data,), daemon=True).start()
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

        # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
            feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                                   __version__)
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        msg_counter = runtime_data["feagi_state"]['burst_counter']
        previous_frame_data = {}
        raw_frame = []
        default_capabilities = {}  # It will be generated in process_visual_stimuli. See the
        # overwrite manual
        previous_burst = 0
        default_capabilities = pns.create_runtime_default_list(default_capabilities, capabilities)
        threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
        threading.Thread(target=retina.vision_progress,
                         args=(default_capabilities, feagi_opu_channel, api_address, feagi_settings,
                               camera_data['vision'],), daemon=True).start()
        while True:
            try:
                if np.any(rgb_array['current']):
                    if not webcam_size['size']:
                        webcam_size['size'].append(rgb_array['current'].pop(0))
                        webcam_size['size'].append(rgb_array['current'].pop(0))
                    raw_frame = retina.RGB_list_to_ndarray(rgb_array['current'],
                                                           webcam_size['size'])
                    raw_frame = retina.update_astype(raw_frame)
                    if 'camera' in default_capabilities:
                        if default_capabilities['camera']['blink'] != []:
                            raw_frame = default_capabilities['camera']['blink']
                    previous_frame_data, rgb, default_capabilities = \
                        retina.process_visual_stimuli(
                            raw_frame,
                            default_capabilities,
                            previous_frame_data,
                            rgb, capabilities)
                    default_capabilities['camera']['blink'] = []
                    message_to_feagi = pns.generate_feagi_data(rgb, msg_counter, datetime.now(),
                                                               message_to_feagi)
                    # if previous_burst != feagi_settings['feagi_burst_speed']:
                    #     ws.append({"newRefreshRate": feagi_settings['feagi_burst_speed']})
                    #     previous_burst = feagi_settings['feagi_burst_speed']
                message_to_feagi = sensors.add_agent_status(connected_agents['0'],
                                                            message_to_feagi,
                                                            agent_settings)
                pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings, feagi_settings)
                sleep(feagi_settings['feagi_burst_speed'])  # bottleneck
                message_to_feagi.clear()
                if 'camera' in rgb:
                    for i in rgb['camera']:
                        rgb['camera'][i].clear()
            except Exception as e:
                # pass
                print("ERROR! : ", e, " and resize: ", pns.resize_list)
                traceback.print_exc()
                break
