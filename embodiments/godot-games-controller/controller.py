#!/usr/bin/env python
"""
Copyright 2016-2023 The FEAGI Authors. All Rights Reserved.
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

import asyncio
import zlib
import threading
from collections import deque
from datetime import datetime
from time import sleep
from version import __version__
from feagi_agent import pns_gateway as pns
import websockets
from configuration import *
from feagi_agent import retina as retina
from feagi_agent import sensors
from feagi_agent import feagi_interface as feagi
import numpy as np
import array
import traceback

ws = deque()
zmq_queue = deque()
old_data = 0
runtime_data = {"cortical_data": {}, "current_burst_id": None, "stimulation_period": 0.01,
                "feagi_state": None, "feagi_network": None, 'accelerator': {}}
camera_data = {"vision": None}


async def echo(websocket):
    """
    The function echoes the data it receives from other connected websockets
    and sends the data from FEAGI to the connected websockets.
    """
    async for message in websocket:
        global old_data
        if not ws_operation:
            ws_operation.append(websocket)
        else:
            ws_operation[0] = websocket
        try:
            if message != b'{}':
                zmq_queue.append(message)
        except Exception as error:
            if "stimulation_period" in runtime_data:
                sleep(runtime_data["stimulation_period"])
            pass
            # print("ERROR!: ", error)
            # traceback.print_exc()


def godot_to_feagi():
    while True:
        if len(zmq_queue) > 0:
            if len(zmq_queue) > 2:
                stored_value = zmq_queue.pop()
                zmq_queue.clear()
                zmq_queue.append(stored_value)
            message = zmq_queue[0]
            obtain_list = list(message)
            if len(obtain_list) == 1:
                zmq_queue.pop()
                gyro['gyro']['0'] = obtain_list[0] - 90
                gyro['gyro']['1'] = 0
                gyro['gyro']['2'] = 0
            else:
                message = zlib.decompress(message)
                string_array = array.array('B', message)
                try:
                    total = len(string_array) - (capabilities['camera']['current_select'][0][0] *
                                                 capabilities['camera']['current_select'][0][1] * 3)
                    last_eight_elements = list(string_array[len(string_array) - total:])
                    ascii_string = ''.join(chr(value) for value in last_eight_elements)
                    values = [float(val) for val in ascii_string.split("/")]
                    if acc:  # This is defined in main. It's a dict
                        acc['accelerator'] = values
                    string_array = string_array[:-total]
                except Exception as error:
                    acc['accelerator'].clear()
                # Debug ends
                # if len(string_array) == (capabilities['camera']['current_select'][0][0] * capabilities[
                #     'camera']['current_select'][0][1] * 3):
                new_cam = np.array(string_array)
                new_cam = new_cam.astype(np.uint8)
                if len(new_cam) == 49152:
                    image = new_cam.reshape(128, 128, 3)
                if len(new_cam) == 3072:
                    image = new_cam.reshape(32, 32, 3)
                if len(new_cam) == 1228800:
                    image = new_cam.reshape(640, 640, 3)
                camera_data['vision'] = image
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
                WS_STRING['motion_control'][str(data_point)] = obtained_data['motion_control'][
                                                                   data_point] * 100
    if 'motor' in obtained_data:
        WS_STRING['motor'] = {}
        for data_point in obtained_data['motor']:
            WS_STRING['motor'][str(data_point)] = obtained_data['motor'][data_point] - 5
    if 'misc' in obtained_data:
        WS_STRING['misc'] = {}
        for data_point in obtained_data['misc']:
            WS_STRING['misc'][str(data_point)] = obtained_data['misc'][data_point]
    ws.append(WS_STRING)


def feagi_main(feagi_auth_url, feagi_settings, agent_settings, capabilities, message_to_feagi):
    global runtime_data
    previous_data_frame = {}
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
    default_capabilities = {}  # It will be generated in update_region_split_downsize. See the
    # overwrite manual
    default_capabilities = pns.create_runtime_default_list(default_capabilities, capabilities)
    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
    threading.Thread(target=retina.vision_progress,
                     args=(default_capabilities, feagi_opu_channel, api_address, feagi_settings,
                           camera_data['vision'],), daemon=True).start()
    while True:
        # Decompression section starts
        message_from_feagi = pns.message_from_feagi
        if message_from_feagi:
            obtained_signals = pns.obtain_opu_data(message_from_feagi)
            action(obtained_signals)
        # OPU section ENDS
        if camera_data['vision'] is not None and camera_data['vision'].any():
            raw_frame = camera_data['vision']
            default_capabilities['camera']['blink'] = []
            if 'camera' in default_capabilities:
                if default_capabilities['camera']['blink'] != []:
                    raw_frame = default_capabilities['camera']['blink']
            previous_frame_data, rgb, default_capabilities = retina.update_region_split_downsize(
                raw_frame,
                default_capabilities,
                previous_frame_data,
                rgb, capabilities)
            message_to_feagi = pns.generate_feagi_data(rgb, msg_counter, datetime.now(),
                                                       message_to_feagi)

        # Add accelerator section
        try:
            if acc['accelerator']:
                runtime_data['accelerator']['0'] = acc['accelerator'][0]
                runtime_data['accelerator']['1'] = acc['accelerator'][1]
                runtime_data['accelerator']['2'] = acc['accelerator'][2]
                if "data" not in message_to_feagi:
                    message_to_feagi["data"] = {}
                if "sensory_data" not in message_to_feagi["data"]:
                    message_to_feagi["data"]["sensory_data"] = {}
                message_to_feagi["data"]["sensory_data"]['accelerator'] = runtime_data[
                    'accelerator']
        except Exception as ERROR:
            print("ERROR: ", ERROR)
            message_to_feagi["data"]["sensory_data"]['accelerator'] = {}
        # End accelerator section
        message_to_feagi = sensors.add_gyro_to_feagi_data(gyro['gyro'], message_to_feagi)
        gyro['gyro'].clear()

        sleep(feagi_settings['feagi_burst_speed'])
        pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings)
        message_to_feagi.clear()


if __name__ == '__main__':
    from configuration import feagi_settings, agent_settings, capabilities, message_to_feagi

    ws_operation = deque()
    acc = {}
    gyro = {}
    capabilities['camera']['current_select'] = [[32, 32], []]
    acc['accelerator'] = {}
    gyro['gyro'] = {}
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