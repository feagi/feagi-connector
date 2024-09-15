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
connected_agents['capabilities'] = {}
camera_data = {"vision": {}}
runtime_data = {"cortical_data": {}, "current_burst_id": None,
                "stimulation_period": 0.01, "feagi_state": None,
                "feagi_network": None}

feagi.validate_requirements('requirements.txt')  # you should get it from the boilerplate generator


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
                    json_data = json.dumps(ws[0])
                    await ws_operation[0].send(json_data)
                    print("sent ws")
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
    try:
        ws.append({"newRefreshRate": 60})
        async for message in websocket:
            connected_agents['0'] = True  # Since this section gets data from client, its marked as true
            if not ws_operation:
                ws_operation.append(websocket)
            else:
                ws_operation[0] = websocket
            decompressed_data = lz4.frame.decompress(message)
            if connected_agents['capabilities']:
                rgb_array['current'] = list(decompressed_data)
                webcam_size['size'].append(rgb_array['current'].pop(0))
                webcam_size['size'].append(rgb_array['current'].pop(0))
            else:
                if not 'current' in rgb_array:
                    rgb_array['current'] = None
                if rgb_array['current'] is None:
                    new_data = json.loads(decompressed_data)
                    if 'capabilities' in new_data:
                        connected_agents['capabilities'] = new_data['capabilities']
    except Exception as error:
        if "stimulation_period" in runtime_data:
            sleep(runtime_data["stimulation_period"])
        pass
        # print("ERROR!: ", error)
        # traceback.print_exc()
    connected_agents['0'] = False  # Once client disconnects, mark it as false
    camera_data['vision'] = None
    rgb_array['current'] = None
    webcam_size['size'] = []


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


def feagi_main(feagi_auth_url, feagi_settings, agent_settings, message_to_feagi, capabilities):
    global runtime_data
    rgb = {}
    rgb['camera'] = {}
    rgb_array['current'] = {}
    feagi_flag = False
    print("Waiting on FEAGI...")
    while not feagi_flag:
        feagi_flag = feagi.is_FEAGI_reachable(os.environ.get('FEAGI_HOST_INTERNAL',
                                                             "127.0.0.1"),
                                              int(os.environ.get('FEAGI_OPU_PORT', "3000")))
        sleep(2)
    print("DONE")

    # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
        feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                               __version__)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    previous_frame_data = {}
    raw_frame = []
    default_capabilities = {}  # It will be generated in process_visual_stimuli. See the
    # overwrite manual
    default_capabilities = pns.create_runtime_default_list(default_capabilities, capabilities)
    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
    threading.Thread(target=retina.vision_progress,
                     args=(default_capabilities, feagi_settings, camera_data,), daemon=True).start()
    while connected_agents['0']:
        message_from_feagi = pns.message_from_feagi
        if message_from_feagi:
            obtained_signals = {}
            obtained_signals['activation_regions'] = []
            for data_point in message_from_feagi['opu_data']['ov_reg']:
                obtained_signals['activation_regions'].append(feagi.block_to_array(data_point))
            if obtained_signals['activation_regions']:
                ws.append(obtained_signals)
        try:
            if np.any(rgb_array['current']):
                raw_frame = retina.RGB_list_to_ndarray(rgb_array['current'],
                                                       webcam_size['size'])
                raw_frame = retina.update_astype(raw_frame)
                camera_data["vision"] = raw_frame
                previous_frame_data, rgb, default_capabilities = \
                    retina.process_visual_stimuli(
                        raw_frame,
                        default_capabilities,
                        previous_frame_data,
                        rgb, capabilities)
                message_to_feagi = pns.generate_feagi_data(rgb, message_to_feagi)
            message_to_feagi = sensors.add_agent_status(connected_agents['0'],
                                                        message_to_feagi,
                                                        agent_settings)
            pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings, feagi_settings)
            sleep(feagi_settings['feagi_burst_speed'])  # bottleneck
            if 'camera' in rgb:
                for i in rgb['camera']:
                    rgb['camera'][i].clear()
        except Exception as e:
            # pass
            print("ERROR! : ", e, " and resize: ", pns.resize_list)
            traceback.print_exc()
            break
    connected_agents['capabilities'] = {}


if __name__ == '__main__':
    # NEW JSON UPDATE
    configuration = feagi.build_up_from_configuration()
    feagi_settings = configuration["feagi_settings"]
    agent_settings = configuration['agent_settings']
    # capabilities = configuration['capabilities']
    feagi_settings['feagi_host'] = os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1")
    feagi_settings['feagi_api_port'] = os.environ.get('FEAGI_API_PORT', "8000")
    agent_settings['godot_websocket_port'] = os.environ.get('WS_WEBCAM_PORT', "9051")
    message_to_feagi = {"data": {}}
    # END JSON UPDATE

    ws_operation = deque()
    acc = {}
    gyro = {}
    prox = {}
    acc['accelerator'] = {}
    prox['proximity'] = {}

    # gyro['gyro'] = []
    threading.Thread(target=websocket_operation, daemon=True).start()
    threading.Thread(target=bridge_operation, args=(runtime_data,), daemon=True).start()
    # while not connected_agents['capabilities']:
    #     sleep(2)
    while True:
        print("Waiting on a device to connect....")
        flag = True
        while flag:
            if connected_agents['capabilities']:
                feagi_settings['feagi_host'] = os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1")
                feagi_settings['feagi_api_port'] = os.environ.get('FEAGI_API_PORT', "8000")
                agent_settings['godot_websocket_port'] = os.environ.get('WS_GODOT_GENERIC_PORT', "9055")
                flag = False
            sleep(0.1)  # Repeated but inside loop

        feagi_auth_url = feagi_settings.pop('feagi_auth_url', None)
        print("FEAGI AUTH URL ------- ", feagi_auth_url)
        try:
            feagi_main(feagi_auth_url, feagi_settings, agent_settings,
                       message_to_feagi, connected_agents['capabilities'])
        except Exception as e:
            print(f"Controller run failed", e)
            traceback.print_exc()
            sleep(2)
