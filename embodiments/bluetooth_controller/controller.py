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

import asyncio
import threading
from collections import deque
from datetime import datetime
from time import sleep
import traceback
import websockets
from version import __version__
from feagi_connector import pns_gateway as pns
from feagi_connector import sensors as sensors
from feagi_connector import actuators
from feagi_connector import feagi_interface as feagi
import os
import json
import numpy

ws = deque()
ws_operation = deque()
previous_data = ""
servo_status = {}
gyro = {}
current_device = {}
connected_agents = dict()  # Initalize
connected_agents['0'] = False  # By default, it is not connected by client's websocket
muse_data = {}


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
                print("error: ", error)
                sleep(0.001)
        else:
            sleep(0.001)


def feagi_to_petoi_id(device_id):
    mapping = {
        0: 0,
        1: 8,
        2: 12,
        3: 9,
        4: 13,
        5: 11,
        6: 15,
        7: 10,
        8: 14
    }
    return mapping.get(device_id, None)


def petoi_listen(message, full_data):
    global gyro
    try:
        if '#' in message:
            cleaned_data = message.replace('\r', '')
            cleaned_data = cleaned_data.replace('\n', '')
            test = cleaned_data.split('#')
            new_data = full_data + test[0]
            new_data = new_data.split(",")
            processed_data = []
            for i in new_data:
                full_number = str()
                for x in i:
                    if x in [".", "-"] or x.isdigit():
                        full_number += x
                if full_number:
                    processed_data.append(float(full_number))
            # Add gyro data into feagi data
            gyro['gyro'] = {'0': processed_data[0], '1': processed_data[1],
                            '2': processed_data[2]}
            full_data = test[1]
        else:
            full_data = message
    except Exception as Error_case:
        pass
    return full_data
    # print("error: ", Error_case)
    # traceback.print_exc()
    # print("raw: ", message)


def microbit_listen(message):
    global microbit_data
    ir_list = []
    if message[0] == 'f':
        pass
    else:
        ir_list.append(0)
    if message[1] == 'f':
        pass
    else:
        ir_list.append(1)
    try:
        x_acc = int(message[2:6])
        y_acc = int(message[6:10])
        z_acc = int(message[10:14])
        ultrasonic = float(message[14:16])
        sound_level = int(message[16:18])
        # Store values in dictionary
        microbit_data['ir'] = ir_list
        microbit_data['ultrasonic'] = ultrasonic / 25
        microbit_data['acceleration'] = {0: x_acc, 1: y_acc, 2: z_acc}
        microbit_data['sound_level'] = {sound_level}
        return
    except Exception as Error_case:
        pass
        # print("error: ", Error_case)
        # print("raw: ", message)


def bridge_operation():
    asyncio.run(bridge_to_godot())


async def echo(websocket, path):
    """
    The function echoes the data it receives from other connected websockets
    and sends the data from FEAGI to the connected websockets.
    """
    current_device['name'] = []
    full_data = ''
    async for message in websocket:
        data_from_bluetooth = json.loads(message)
        for device_name in data_from_bluetooth:
            connected_agents['0'] = True  # Since this section gets data from client, its marked as true
            if device_name not in current_device['name']:
                current_device['name'].append(device_name)
            if not ws_operation:
                ws_operation.append(websocket)
            else:
                ws_operation[0] = websocket

            if device_name == "microbit":
                microbit_listen(data_from_bluetooth['microbit']['data'])
            elif device_name == "petoi":
                full_data = petoi_listen(data_from_bluetooth['petoi'], full_data)  # Needs to add
            elif device_name == "muse":
                muse_listen(data_from_bluetooth['muse'])
            elif device_name == "generic":
                print("generic")
                pass  # Needs to figure how to address this
            else:
                print("unknown device")
                print("message: ", data_from_bluetooth)
    connected_agents['0'] = False  # Once client disconnects, mark it as false
    muse_data.clear()
    current_device['name'].clear()
    for i in microbit_data:
        if isinstance(microbit_data[i], dict):
            microbit_data[i].clear()
        else:
            microbit_data[i] = None



async def main():
    """
    The main function handles the websocket and spins the asyncio to run the echo function
    infinitely until it exits. Once it exits, the function will resume to the next new websocket.
    """
    async with websockets.serve(echo, agent_settings["godot_websocket_ip"],
                                agent_settings['godot_websocket_port']):
        await asyncio.Future()  # run forever


def websocket_operation():
    """
    WebSocket initialized to call the echo function using asyncio.
    """
    asyncio.run(main())


def muse_listen(obtained_data):
    dict_from_muse = obtained_data
    if dict_from_muse['type'] not in muse_data:
        muse_data[dict_from_muse['type']] = {}
    if dict_from_muse['type'] == 'eeg':
        muse_data['eeg'][dict_from_muse['data']['electrode']] = dict_from_muse['data']['samples']
    if dict_from_muse['type'] == 'acceleration':
        for i in range(len(dict_from_muse['data']['samples'])):
            muse_data['acceleration'][i] = dict_from_muse['data']['samples'][i]
    if dict_from_muse['type'] == 'telemetry':
        muse_data['telemetry']['battery'] = dict_from_muse['data']['batteryLevel']


def petoi_action(obtained_data):
    servo_data = actuators.get_servo_data(obtained_data, True)
    WS_STRING = ""
    if 'servo_position' in obtained_data:
        servo_for_feagi = 'i '
        if obtained_data['servo_position'] is not {}:
            for data_point in obtained_data['servo_position']:
                device_id = feagi_to_petoi_id(data_point)
                encoder_position = (((180) / 20) * obtained_data['servo_position'][data_point]) - 90
                servo_for_feagi += str(device_id) + " " + str(encoder_position) + " "
            WS_STRING += servo_for_feagi
    if servo_data:
        WS_STRING = "i"
        for device_id in servo_data:
            servo_power = actuators.servo_generate_power(180, servo_data[device_id], device_id)
            if device_id not in servo_status:
                servo_status[device_id] = actuators.servo_keep_boundaries(90)
            else:
                servo_status[device_id] += servo_power / 10
                servo_status[device_id] = actuators.servo_keep_boundaries(servo_status[device_id])
            actual_id = feagi_to_petoi_id(device_id)
            # print("device id: ", actual_id, ' and power: ', servo_data[device_id], " servo power: ", servo_power)
            WS_STRING += " " + str(actual_id) + " " + str(
                int(actuators.servo_keep_boundaries(servo_status[device_id])) - 90)
    if WS_STRING != "":
        # WS_STRING = WS_STRING + "#"
        print("sending to main: ", WS_STRING)
        ws.append(WS_STRING)


def microbit_action(obtained_data):
    recieve_motor_data = actuators.get_motor_data(obtained_data)
    WS_STRING = ""

    if recieve_motor_data:
        updated_motor=0
        for motor_id in [0, 1]:
            data_power = 0
            if motor_id in recieve_motor_data:
                data_power = recieve_motor_data[motor_id]
                if data_power == 100:
                    data_power -= 1
                elif data_power == -100:
                    data_power += 1

            if motor_id == 0:
                if data_power < 0:
                    updated_motor = 1
            elif motor_id == 1:
                if data_power < 0:
                    updated_motor = 3
                else:
                    updated_motor = 2
            WS_STRING += str(updated_motor) + str(abs(data_power)).zfill(2)

    if WS_STRING == "000200":
        WS_STRING = ""  # so we don't spam microbit with no power

    if WS_STRING != "":
        WS_STRING = WS_STRING + "#"
        ws.append(WS_STRING)


if __name__ == "__main__":

    # NEW JSON UPDATE
    configuration = feagi.build_up_from_configuration()
    feagi_settings = configuration["feagi_settings"]
    agent_settings = configuration['agent_settings']
    capabilities = configuration['capabilities']
    feagi_settings['feagi_host'] = os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1")
    feagi_settings['feagi_api_port'] = os.environ.get('FEAGI_API_PORT', "8000")
    agent_settings['godot_websocket_port'] = os.environ.get('WS_MICROBIT_PORT', "9052")
    message_to_feagi = {}
    # END JSON UPDATE

    microbit_data = {'ir': [], 'ultrasonic': {}, 'acceleration': {}, 'sound_level': {}}
    threading.Thread(target=websocket_operation, daemon=True).start()
    # threading.Thread(target=bridge_to_godot, daemon=True).start()
    threading.Thread(target=bridge_operation, daemon=True).start()
    feagi_flag = False
    print("Waiting on FEAGI...")
    while not feagi_flag:
        feagi_flag = feagi.is_FEAGI_reachable(
            os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1"),
            int(os.environ.get('FEAGI_OPU_PORT', "3000"))
        )
        sleep(2)
    previous_data_frame = {}
    runtime_data = {"cortical_data": {}, "current_burst_id": None,
                    "stimulation_period": 0.01, "feagi_state": None,
                    "feagi_network": None}

    feagi_auth_url = feagi_settings.pop('feagi_auth_url', None)
    print("FEAGI AUTH URL ------- ", feagi_auth_url)

    # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # - - - - - - - - - - - - - - - - - - #
    feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
        feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                               __version__)
    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    msg_counter = runtime_data["feagi_state"]['burst_counter']
    runtime_data['acceleration'] = {}

    actuators.start_motors(capabilities)  # initialize motors for you.

    while True:
        try:
            message_from_feagi = pns.message_from_feagi
            # OPU section STARTS
            if message_from_feagi:
                pns.check_genome_status_no_vision(message_from_feagi)
                feagi_settings['feagi_burst_speed'] = pns.check_refresh_rate(message_from_feagi, feagi_settings['feagi_burst_speed'])
                obtained_signals = pns.obtain_opu_data(message_from_feagi)
                if 'name' in current_device:
                    if "microbit" in current_device['name']:
                        microbit_action(obtained_signals)
                    elif "petoi" in current_device['name']:
                        petoi_action(obtained_signals)

            # OPU section ENDS
            if microbit_data['ultrasonic']:
                message_to_feagi = sensors.create_data_for_feagi(sensor='proximity', capabilities=capabilities, message_to_feagi=message_to_feagi,
                                                                 current_data=microbit_data['ultrasonic'], measure_enable=True)

            if microbit_data['acceleration']:
                if pns.full_template_information_corticals:
                    message_to_feagi = sensors.convert_ir_to_ipu_data(microbit_data['ir'], len(capabilities['input']['infrared']), message_to_feagi)
                    # The IR will need to turn the inverse IR on if it doesn't detect. This would confuse humans when
                    # cutebot is not on. So the solution is to put this under the acceleration. It is under acceleration
                    # because without acceleration, the micro:bit is not on. This leverages the advantage to detect if it
                    # is still on.
                    message_to_feagi = sensors.create_data_for_feagi(sensor='accelerometer', capabilities=capabilities, message_to_feagi=message_to_feagi,
                                                                     current_data=microbit_data['acceleration'], symmetric=True,
                                                                     measure_enable=True)

            message_to_feagi['timestamp'] = datetime.now()
            message_to_feagi['counter'] = msg_counter
            message_to_feagi = sensors.add_agent_status(connected_agents['0'],
                                                        message_to_feagi,
                                                        agent_settings)
            sleep(feagi_settings['feagi_burst_speed'])
            pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings, feagi_settings)
            message_to_feagi.clear()
        except Exception as e:
            print("ERROR: ", e)
            traceback.print_exc()
            break
