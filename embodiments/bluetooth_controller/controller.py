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
    recieve_motor_data = actuators.get_motor_data(obtained_data,
                                                  capabilities['motor']['power_amount'],
                                                  capabilities['motor']['count'], rolling_window)

    WS_STRING = ""
    new_dict = {'motor': {}}
    if 0 in recieve_motor_data:
        if 1 in recieve_motor_data:
            if recieve_motor_data[0] >= recieve_motor_data[1]:
                new_dict['motor'][0] = recieve_motor_data[0]
            else:
                new_dict['motor'][1] = recieve_motor_data[1]
    if 2 in recieve_motor_data:
        if 3 in recieve_motor_data:
            if recieve_motor_data[2] >= recieve_motor_data[3]:
                new_dict['motor'][2] = recieve_motor_data[2]
            else:
                new_dict['motor'][3] = recieve_motor_data[3]
    for i in new_dict['motor']:
        if i in [0, 1]:
            data_power = new_dict['motor'][i]
            if data_power <= 0:
                data_power = 1
            WS_STRING += str(i) + str(data_power - 1).zfill(
                2)  # Append the motor data as a two-digit
            # string
        elif i in [2, 3]:
            data_power = new_dict['motor'][i]
            if data_power <= 0:
                data_power = 1
            WS_STRING += str(i) + str(data_power - 1).zfill(
                2)  # Append the motor data as a two-digit
    if WS_STRING != "":
        WS_STRING = WS_STRING + "#"
        ws.append(WS_STRING)


if __name__ == "__main__":

    # NEW JSON UPDATE
    f = open('configuration.json')
    configuration = json.load(f)
    feagi_settings = configuration["feagi_settings"]
    agent_settings = configuration['agent_settings']
    capabilities = configuration['capabilities']
    feagi_settings['feagi_host'] = os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1")
    feagi_settings['feagi_api_port'] = os.environ.get('FEAGI_API_PORT', "8000")
    agent_settings['godot_websocket_port'] = os.environ.get('WS_MICROBIT_PORT', "9052")
    f.close()
    message_to_feagi = {"data": {}}
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
    rolling_window = {}
    rolling_window_len = capabilities['motor']['rolling_window_len']
    motor_count = capabilities['motor']['count']

    # Initialize rolling window for each motor
    for motor_id in range(motor_count):
        rolling_window[motor_id] = deque([0] * rolling_window_len)

    # Muse's EEG values range
    max_value = []
    min_value = []

    # Muse's acceleration value range
    acceleration_max_value = []
    acceleration_min_value = []

    # Microbit acceleration values
    microbit_acceleration_max_value = []
    microbit_acceleration_min_value = []

    # Microbit Ultrasonic values
    microbit_ultrasonic_max_value = []
    microbit_ultrasonic_min_value = []
    for i in range(4):
        max_value.append(0)
        min_value.append(0)
    while True:
        try:
            message_from_feagi = pns.message_from_feagi
            # OPU section STARTS
            if message_from_feagi:
                pns.check_genome_status_no_vision(message_from_feagi)
                feagi_settings['feagi_burst_speed'] = pns.check_refresh_rate(message_from_feagi,
                                                                             feagi_settings[
                                                                                 'feagi_burst_speed'])
                obtained_signals = pns.obtain_opu_data(message_from_feagi)
                if 'name' in current_device:
                    if "microbit" in current_device['name']:
                        microbit_action(obtained_signals)
                    elif "petoi" in current_device['name']:
                        petoi_action(obtained_signals)
            # OPU section ENDS
            if microbit_data['ultrasonic']:
                ultrasonic_data = {'i__pro': {}}
                microbit_ultrasonic_max_value, microbit_ultrasonic_min_value = \
                    sensors.measuring_max_and_min_range(microbit_data['ultrasonic'],
                                                        0,
                                                        microbit_ultrasonic_max_value,
                                                        microbit_ultrasonic_min_value)
                position = sensors.convert_sensor_to_ipu_data(microbit_ultrasonic_min_value[0],
                                                              microbit_ultrasonic_max_value[0],
                                                              microbit_data['ultrasonic'], 0,
                                                              cortical_id='i__pro')
                ultrasonic_data['i__pro'][position] = 100
                message_to_feagi = sensors.add_generic_input_to_feagi_data(ultrasonic_data,
                                                                        message_to_feagi)

            if microbit_data['acceleration']:
                # The IR will need to turn the inverse IR on if it doesn't detect. This would confuse humans when cutebot
                # is not on. So the solution is to put this under the acceleration.
                # It is under acceleration because without acceleration, the micro:bit is not on.
                # This leverages the advantage to detect if it is still on.
                ir_active, inverse_ir_active = sensors.convert_ir_to_ipu_data(microbit_data['ir'],
                                                                              capabilities['infrared']['count'])
                message_to_feagi = sensors.add_generic_input_to_feagi_data(ir_active,
                                                                           message_to_feagi)
                message_to_feagi = sensors.add_generic_input_to_feagi_data(inverse_ir_active,
                                                                           message_to_feagi)
                # End of IR section

                # Section of acceleration
                create_acceleration_data_list_microbit = dict()
                create_acceleration_data_list_microbit['i__acc'] = dict()
                for device_id in capabilities['acceleration']['microbit']:
                    microbit_acceleration_max_value, microbit_acceleration_min_value = (
                        sensors.measuring_max_and_min_range(microbit_data['acceleration'][device_id],
                                                            device_id,
                                                            microbit_acceleration_max_value,
                                                            microbit_acceleration_min_value))
                    try:
                        position_of_analog = sensors.convert_sensor_to_ipu_data(microbit_acceleration_min_value[device_id],
                                                                                microbit_acceleration_max_value[device_id],
                                                                                microbit_data['acceleration'][device_id],
                                                                                device_id,
                                                                                cortical_id='i__acc',
                                                                                symmetric=True)
                        create_acceleration_data_list_microbit['i__acc'][position_of_analog] = 100
                    except:
                        pass
                message_to_feagi = sensors.add_generic_input_to_feagi_data(create_acceleration_data_list_microbit,
                                                                 message_to_feagi)

            if gyro:
                message_to_feagi = sensors.add_gyro_to_feagi_data(gyro['gyro'], message_to_feagi)

            if muse_data:
                if 'eeg' in muse_data:
                    convert_eeg_to_ipu = dict()
                    create_analog_data_list = dict()
                    create_analog_data_list['i__bci'] = dict()
                    for number in muse_data['eeg']:
                        channel = number
                        convert_eeg_to_ipu[channel] = muse_data['eeg'][number][len(muse_data['eeg'][number]) - 1]
                        convert_to_numpy = numpy.array(muse_data['eeg'][number])
                        if convert_to_numpy.max() > max_value[channel]:
                            max_value[channel] = convert_to_numpy.max()
                        if convert_to_numpy.min() < min_value[channel]:
                            min_value[channel] = convert_to_numpy.min()
                        position_of_analog = str(channel) + "-0-0"
                        create_analog_data_list['i__bci'][position_of_analog] = convert_eeg_to_ipu[channel] + 1000.0
                    message_to_feagi = sensors.add_generic_input_to_feagi_data(create_analog_data_list,
                                                                               message_to_feagi)
                acceleration_from_muse = dict()
                if 'acceleration' in muse_data:
                    counter = 0
                    create_acceleration_data_list = dict()
                    create_acceleration_data_list['i__acc'] = dict()
                    for i in range(len(muse_data['acceleration'])):
                        for x in muse_data['acceleration'][i]:
                            increment = counter
                            acceleration_from_muse[increment] = muse_data['acceleration'][i][x]
                            acceleration_max_value, acceleration_min_value = (
                                sensors.measuring_max_and_min_range(muse_data['acceleration'][i][x],
                                                                    increment,
                                                                    acceleration_max_value,
                                                                    acceleration_min_value))
                            try:
                                position_of_analog = sensors.convert_sensor_to_ipu_data(acceleration_min_value[increment],
                                                                                        acceleration_max_value[increment],
                                                                                        muse_data['acceleration'][i][x],
                                                                                        increment + 3, cortical_id='i__acc',
                                                                                        symmetric=True)
                                create_acceleration_data_list['i__acc'][position_of_analog] = 100
                                counter += 1
                            except Exception as error:
                                position_of_analog = None
                                counter += 1
                    message_to_feagi = sensors.add_generic_input_to_feagi_data(create_acceleration_data_list,
                                                                     message_to_feagi)
                # if 'telemetry' in muse_data:
                #     battery = dict()
                #     battery['i__bat'] = dict()
                #     convert_battery_to_IPU = sensors.convert_sensor_to_ipu_data(0,
                #                                                             100,
                #                                                             muse_data['telemetry']['battery'],
                #                                                             0, cortical_id='i__bat')
                #     print("convert_battery_to_IPU: ", convert_battery_to_IPU, " and type: ", type(convert_battery_to_IPU))
                #     battery['i__bat'][convert_battery_to_IPU] = 100
                #     message_to_feagi = sensors.add_generic_input_to_feagi_data(convert_battery_to_IPU,
                #                                                                message_to_feagi)



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
