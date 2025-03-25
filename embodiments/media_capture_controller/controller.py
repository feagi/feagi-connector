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
import ast
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
cortical_used_list = ['o___id', 'o__loc', 'o__sid', 'opoint', 'o_misc']


def expand_pixel(xyz_array, radius, width, height):
    """
    Expands each pixel in the input array by creating a square of pixels around it

    Args:
        xyz_array: numpy array of shape (N, 3) containing x,y coordinates
        radius: int, how many pixels to expand in each direction
        width: int, maximum width of the image
        height: int, maximum height of the image
    """
    # Create the offset ranges
    x_offsets = np.arange(-radius, radius)
    y_offsets = np.arange(-radius, radius)

    # Create meshgrid of offsets
    xx, yy = np.meshgrid(x_offsets, y_offsets)
    offsets = np.column_stack((xx.ravel(), yy.ravel()))

    # Expand the original array to match offsets shape
    expanded = xyz_array[:, np.newaxis, :]  # Shape becomes (1083, 1, 3)

    # Broadcasting magic happens here
    new_coords = expanded[:, :, :2] + offsets[np.newaxis, :, :]  # Add offsets to x,y coordinates

    # Clip to image boundaries
    new_coords[:, :, 0] = np.clip(new_coords[:, :, 0], 0, width)
    new_coords[:, :, 1] = np.clip(new_coords[:, :, 1], 0, height)

    # If there's a third column (e.g., intensity), repeat it for all expanded pixels
    if xyz_array.shape[1] > 2:
        new_values = np.repeat(xyz_array[:, 2:], offsets.shape[0]).reshape(xyz_array.shape[0], offsets.shape[0], -1)
        new_coords = np.concatenate([new_coords, new_values], axis=2)

    # Reshape to 2D array
    result = new_coords.reshape(-1, xyz_array.shape[1])

    return result

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
                    ws.pop()
                sleep(runtime_data["stimulation_period"])
            except Exception as error:
                # print("error in websocket sender: ", error)
                # traceback.print_exc()
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
        async for message in websocket:
            connected_agents['0'] = True  # Since this section gets data from client, its marked as true
            if not ws_operation:
                ws_operation.append(websocket)
            else:
                ws_operation[0] = websocket
            decompressed_data = lz4.frame.decompress(message)
            if connected_agents['capabilities']:
                try:
                    cortical_stimulation['current'] = json.loads(decompressed_data)
                except:
                    new_list = list(decompressed_data)
                    webcam_size['size'].append(new_list.pop(0))
                    webcam_size['size'].append(new_list.pop(0))
                    raw_frame = retina.RGB_list_to_ndarray(new_list,
                                                           webcam_size['size'])
                    rgb_array['current'] = {"0": retina.update_astype(raw_frame)}

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
        print("ERROR!: ", error)
        traceback.print_exc()
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
    rgb_data_for_feagi = {}
    rgb_data_for_feagi['camera'] = {}
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
            # obtained_signals = {}
            # obtained_signals = retina.activation_region_break_down(message_from_feagi, obtained_signals)
            # if obtained_signals:
            #     if 'camera' in default_capabilities['input']:
            #         obtained_signals['modulation_control'] = default_capabilities['input']['camera']['0']['modulation_control']
            #         obtained_signals['eccentricity_control'] = default_capabilities['input']['camera']['0']['eccentricity_control']
            # temp:
            if 'ov_out' in message_from_feagi['opu_data']:
                original_frame_size = raw_frame.shape
                converted_array = np.array(list(message_from_feagi['opu_data']['ov_out']))
                if converted_array.ndim == 1:
                    converted_array = converted_array.reshape(-1, 2)
                converted_array[:, 0] = converted_array[:, 0] + 0.3
                converted_array[:, 0] = (converted_array[:, 0] * original_frame_size[1]) / \
                                        pns.full_list_dimension['ov_out']['cortical_dimensions'][0]
                converted_array[:, 1] = converted_array[:, 1] * -1 + \
                                        pns.full_list_dimension['ov_out']['cortical_dimensions'][1]
                converted_array[:, 1] = ((converted_array[:, 1] * original_frame_size[0]) /
                                         pns.full_list_dimension['ov_out']['cortical_dimensions'][
                                             1]).astype(int)
                expanded_coords = expand_pixel(converted_array, 10,
                                                               original_frame_size[1],
                                                               original_frame_size[0])
                x = np.clip(expanded_coords[:, 0], 0, original_frame_size[1] - 1).astype(int)
                y = np.clip(expanded_coords[:, 1], 0, original_frame_size[0] - 1).astype(int)
                raw_frame[y, x] = [255, 0, 0]
            ws_data_to_send_from_feagi = {}
            for key in message_from_feagi['opu_data']:
                if key in cortical_used_list:
                    ws_data_to_send_from_feagi[key] = message_from_feagi['opu_data'][key]
            print("here: ", ws_data_to_send_from_feagi)
            ws.append(ws_data_to_send_from_feagi)
        try:
            if np.any(rgb_array['current']):
                raw_frame = rgb_array['current']
                camera_data["vision"] = raw_frame
                previous_frame_data, rgb_data_for_feagi, default_capabilities = \
                    retina.process_visual_stimuli(
                        raw_frame,
                        default_capabilities,
                        previous_frame_data,
                        rgb_data_for_feagi, capabilities)
                message_to_feagi = pns.generate_feagi_data(rgb_data_for_feagi, message_to_feagi)
            message_to_feagi = sensors.add_agent_status(connected_agents['0'],
                                                        message_to_feagi,
                                                        agent_settings)

            if cortical_stimulation['current']:
                if 'cortical_stimulation' in cortical_stimulation['current']:
                    data = {}
                    for i in cortical_stimulation['current']['cortical_stimulation']:
                        for key in cortical_stimulation['current']['cortical_stimulation'][i]:
                            data[i] = {ast.literal_eval(k): v for k, v in cortical_stimulation['current']['cortical_stimulation'][i].items()}
                        message_to_feagi = sensors.add_generic_input_to_feagi_data(data, message_to_feagi)
            pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings, feagi_settings)
            sleep(feagi_settings['feagi_burst_speed'])  # bottleneck
            if 'camera' in rgb_data_for_feagi:
                for i in rgb_data_for_feagi['camera']:
                    rgb_data_for_feagi['camera'][i].clear()
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
    cortical_stimulation = {}
    cortical_stimulation['current'] = {}

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
