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
==============================================================================
"""
import os
import json
import zlib
import array
import asyncio
import traceback
import threading
import websockets
import numpy as np
from time import sleep
from datetime import datetime
from collections import deque
from version import __version__
from feagi_connector import sensors
from feagi_connector import retina as retina
from feagi_connector import pns_gateway as pns
from feagi_connector import feagi_interface as feagi

ws = deque()
zmq_queue = deque()
runtime_data = {"cortical_data": {}, "current_burst_id": None, "stimulation_period": 0.01,
                "feagi_state": None, "feagi_network": None, 'accelerator': {}}
camera_data = {"vision": None}
connected_agents = dict() # Initalize
connected_agents['0'] = False  # By default, it is not connected by client's websocket


async def echo(websocket):
    """
    The function echoes the data it receives from other connected websockets
    and sends the data from FEAGI to the connected websockets.
    """
    try:
        async for message in websocket:
            connected_agents['0'] = True # Since this section gets data from client, its marked as true
            if not ws_operation:
                ws_operation.append(websocket)
            else:
                ws_operation[0] = websocket
            if message != b'{}':
                zmq_queue.append(message)
    except Exception as error:
        if "stimulation_period" in runtime_data:
            sleep(runtime_data["stimulation_period"])
        pass
        # print("ERROR!: ", error)
        # traceback.print_exc()
    connected_agents['0'] = False # Once client disconnects, mark it as false


def godot_to_feagi():
    while True:
        if len(zmq_queue) > 0:
            if len(zmq_queue) > 2:
                stored_value = zmq_queue.pop()
                zmq_queue.clear()
                zmq_queue.append(stored_value)
            message = zmq_queue[0]
            obtain_list = zlib.decompress(message)
            new_data = json.loads(obtain_list)
            if 'gyro' in new_data:
                gyro['gyro'] = new_data['gyro']
            if 'vision' in new_data:
                string_array = new_data['vision']
                new_cam = np.array(string_array)
                new_cam = new_cam.astype(np.uint8)
                if len(new_cam) == 49152:
                    image = new_cam.reshape(128, 128, 3)
                if len(new_cam) == 3072:
                    image = new_cam.reshape(32, 32, 3)
                if len(new_cam) == 1228800:
                    image = new_cam.reshape(640, 640, 3)
                camera_data['vision'] = image
            if 'acceleration' in new_data:
                acc['accelerator'] = new_data['acceleration']
            if 'proximity' in new_data:
                prox['proximity'] = new_data['proximity']
            zmq_queue.pop()
        if "stimulation_period" in runtime_data:
            sleep(runtime_data["stimulation_period"])


async def bridge_to_godot():
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
                if "stimulation_period" in runtime_data:
                    sleep(runtime_data["stimulation_period"])
            except Exception as error:
                # print("error: ", error)
                sleep(0.001)
        else:
            sleep(0.001)


def bridge_operation():
    asyncio.run(bridge_to_godot())


async def main():
    """
    The main function handles the websocket and spins the asyncio to run the echo function
    infinitely until it exits. Once it exits, the function will resume to the next new websocket.
    """
    async with websockets.serve(echo, agent_settings["godot_websocket_ip"],
                                agent_settings['godot_websocket_port'], max_size=None,
                                max_queue=None, write_limit=None):
        await asyncio.Future()  # run forever


def websocket_operation():
    """
    WebSocket initialized to call the echo function using asyncio.
    """
    asyncio.run(main())


def action(obtained_data):
    WS_STRING = {}
    if 'motion_control' in obtained_data:
        WS_STRING['motion_control'] = {}
        for data_point in obtained_data['motion_control']:
            if data_point in ["move_left", "move_right", "move_up", "move_down"]:
                WS_STRING['motion_control'][str(data_point)] = obtained_data['motion_control'][data_point]
                print(WS_STRING)
    if 'motor' in obtained_data:
        WS_STRING['motor'] = {}
        for data_point in obtained_data['motor']:
            WS_STRING['motor'][str(data_point)] = obtained_data['motor'][data_point]
    if 'misc' in obtained_data:
        WS_STRING['misc'] = {}
        for data_point in obtained_data['misc']:
            WS_STRING['misc'][str(data_point)] = obtained_data['misc'][data_point]
    ws.append(WS_STRING)


def feagi_main(feagi_auth_url, feagi_settings, agent_settings, capabilities, message_to_feagi):
    global runtime_data
    feagi_flag = False
    print("retrying...")
    print("Waiting on FEAGI...")
    while not feagi_flag:
        feagi_flag = feagi.is_FEAGI_reachable(
            os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1"),
            int(os.environ.get('FEAGI_OPU_PORT', "3000")))
        sleep(2)

    # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # - - - - - - - - - - - - - - - - - - #
    feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
        feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                               __version__)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    msg_counter = runtime_data["feagi_state"]['burst_counter']
    rgb = dict()
    rgb['camera'] = dict()
    previous_frame_data = {}
    default_capabilities = {}  # It will be generated in process_visual_stimuli. See the
    # overwrite manual
    default_capabilities = pns.create_runtime_default_list(default_capabilities, capabilities)
    threading.Thread(target=retina.vision_progress, args=(default_capabilities,feagi_settings, camera_data,), daemon=True).start()
    while True:
        # Decompression section starts
        message_from_feagi = pns.message_from_feagi
        if message_from_feagi:
            obtained_signals = pns.obtain_opu_data(message_from_feagi)
            action(obtained_signals)
        # OPU section ENDS
        if camera_data['vision'] is not None and camera_data['vision'].any():
            raw_frame = camera_data['vision']
            previous_frame_data, rgb, default_capabilities = retina.process_visual_stimuli(
                raw_frame,
                default_capabilities,
                previous_frame_data,
                rgb, capabilities)
            message_to_feagi = pns.generate_feagi_data(rgb, message_to_feagi)

        # Add accelerator section
        if 'acceleration' in acc:
            for device_id in capabilities['input']['accelerator']:
                if not capabilities['input']['accelerator'][device_id]['disable']:
                    cortical_id = capabilities['input']['accelerator'][device_id]["cortical_id"]
                    create_data_list = dict()
                    create_data_list[cortical_id] = dict()
                    start_point = capabilities['input']['accelerator'][device_id][
                                      "feagi_index"] * len(capabilities['input']['accelerator'])
                    feagi_data_position = start_point
                    try:
                        for device_id in range(
                                len(capabilities['input']['accelerator'][device_id]['max_value'])):
                            capabilities['input']['accelerator'][device_id]['max_value'][device_id], \
                            capabilities['input']['accelerator'][device_id]['min_value'][
                                device_id] = sensors.measuring_max_and_min_range(
                                acc['accelerator'][int(device_id)],
                                capabilities['input']['accelerator'][device_id]['max_value'][device_id],
                                capabilities['input']['accelerator'][device_id]['min_value'][device_id])

                            position_in_feagi_location = sensors.convert_sensor_to_ipu_data(
                                capabilities['input']['accelerator'][device_id]['min_value'][device_id],
                                capabilities['input']['accelerator'][device_id]['max_value'][device_id],
                                acc['accelerator'][int(device_id)],
                                capabilities['input']['accelerator'][device_id][
                                    'feagi_index'] + int(device_id),
                                cortical_id=cortical_id,
                                symmetric=True)
                            create_data_list[cortical_id][position_in_feagi_location] = 100
                        if create_data_list[cortical_id]:
                            message_to_feagi = sensors.add_generic_input_to_feagi_data(
                                create_data_list, message_to_feagi)
                    except:
                        pass

        if 'gyro' in gyro:
            for device_id in capabilities['input']['gyro']:
                if not capabilities['input']['gyro'][device_id]['disable']:
                    cortical_id = capabilities['input']['gyro'][device_id]["cortical_id"]
                    create_data_list = dict()
                    create_data_list[cortical_id] = dict()
                    start_point = capabilities['input']['gyro'][device_id]["feagi_index"] * len(
                        capabilities['input']['gyro'])
                    feagi_data_position = start_point
                    try:
                        for inner_device_id in range(
                                len(capabilities['input']['gyro'][device_id]['max_value'])):
                            capabilities['input']['gyro'][device_id]['max_value'][inner_device_id], \
                            capabilities['input']['gyro'][device_id]['min_value'][
                                inner_device_id] = sensors.measuring_max_and_min_range(
                                gyro['gyro'][inner_device_id],
                                capabilities['input']['gyro'][device_id]['max_value'][inner_device_id],
                                capabilities['input']['gyro'][device_id]['min_value'][inner_device_id])

                            position_in_feagi_location = sensors.convert_sensor_to_ipu_data(
                                capabilities['input']['gyro'][device_id]['min_value'][inner_device_id],
                                capabilities['input']['gyro'][device_id]['max_value'][inner_device_id],
                                gyro['gyro'][inner_device_id],
                                capabilities['input']['gyro'][device_id]['feagi_index'] + int(inner_device_id),
                                cortical_id=cortical_id,
                                symmetric=True)
                            create_data_list[cortical_id][position_in_feagi_location] = 100
                        if create_data_list[cortical_id]:
                            message_to_feagi = sensors.add_generic_input_to_feagi_data(
                                create_data_list, message_to_feagi)
                    except Exception as e:
                        print("here: ", e)
                        traceback.print_exc()

        if 'proximity' in prox:
            if prox['proximity']:
                for device_id in capabilities['input']['proximity']:
                    if not capabilities['input']['proximity'][device_id]['disable']:
                        cortical_id = capabilities['input']['proximity'][device_id]["cortical_id"]
                        create_data_list = dict()
                        create_data_list[cortical_id] = dict()
                        start_point = capabilities['input']['proximity'][device_id][
                                          "feagi_index"] * len(capabilities['input']['proximity'])
                        feagi_data_position = start_point
                        capabilities['input']['proximity'][device_id]['proximity_max_distance'], \
                        capabilities['input']['proximity'][device_id][
                            'proximity_min_distance'] = sensors.measuring_max_and_min_range(
                            prox['proximity'][int(device_id)],
                            capabilities['input']['proximity'][device_id]['proximity_max_distance'],
                            capabilities['input']['proximity'][device_id]['proximity_min_distance'])

                        position_in_feagi_location = sensors.convert_sensor_to_ipu_data(
                            capabilities['input']['proximity'][device_id]['proximity_min_distance'],
                            capabilities['input']['proximity'][device_id]['proximity_max_distance'],
                            prox['proximity'][int(device_id)],
                            capabilities['input']['proximity'][device_id]['feagi_index'] +
                            int(device_id),
                            cortical_id=cortical_id,
                            symmetric=True)
                        create_data_list[cortical_id][position_in_feagi_location] = 100
                        if create_data_list[cortical_id]:
                            message_to_feagi = sensors.add_generic_input_to_feagi_data(create_data_list,
                                                                                       message_to_feagi)

        message_to_feagi = sensors.add_agent_status(connected_agents['0'], message_to_feagi, agent_settings)
        pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings, feagi_settings)
        sleep(feagi_settings['feagi_burst_speed'])
        message_to_feagi.clear()
        if not connected_agents['0']:
            gyro.clear()
            prox.clear()


if __name__ == '__main__':
    # NEW JSON UPDATE
    f = open('configuration.json')
    configuration = json.load(f)
    feagi_settings =  configuration["feagi_settings"]
    agent_settings = configuration['agent_settings']
    capabilities = configuration['capabilities']
    feagi_settings['feagi_host'] = os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1")
    feagi_settings['feagi_api_port'] = os.environ.get('FEAGI_API_PORT', "8000")
    agent_settings['godot_websocket_port'] = os.environ.get('WS_GODOT_GENERIC_PORT', "9055")
    f.close()
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
    threading.Thread(target=bridge_operation, daemon=True).start()
    threading.Thread(target=godot_to_feagi, daemon=True).start()
    while True:
        feagi_auth_url = feagi_settings.pop('feagi_auth_url', None)
        print("FEAGI AUTH URL ------- ", feagi_auth_url)
        try:
            feagi_main(feagi_auth_url, feagi_settings, agent_settings, capabilities,
                       message_to_feagi)
        except Exception as e:
            print(f"Controller run failed", e)
            traceback.print_exc()
            sleep(2)