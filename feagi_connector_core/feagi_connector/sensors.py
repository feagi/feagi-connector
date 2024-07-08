#!/usr/bin/env python3
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
import traceback
import time
from feagi_connector import pns_gateway as pns

#
# def add_infrared_to_feagi_data(ir_list, message_to_feagi, capabilities):
#     formatted_ir_data = {sensor: True for sensor in ir_list}
#     for ir_sensor in range(int(capabilities['infrared']['count'])):
#         if ir_sensor not in formatted_ir_data:
#             formatted_ir_data[ir_sensor] = False
#     return pns.append_sensory_data_for_feagi('ir', formatted_ir_data, message_to_feagi)
#
#
# def add_ultrasonic_to_feagi_data(ultrasonic_list, message_to_feagi):
#     formatted_ultrasonic_data = {sensor: data for sensor, data in enumerate([ultrasonic_list])}
#     return pns.append_sensory_data_for_feagi('ultrasonic', formatted_ultrasonic_data,
#                                              message_to_feagi)
#
#
# def add_battery_to_feagi_data(battery_list, message_to_feagi):
#     formatted_battery_data = {sensor: data for sensor, data in enumerate([battery_list])}
#     return pns.append_sensory_data_for_feagi('battery', formatted_battery_data,
#                                              message_to_feagi)
#
#
# def add_gyro_to_feagi_data(gyro_list, message_to_feagi):
#     return pns.append_sensory_data_for_feagi('gyro', gyro_list, message_to_feagi)
#
#
# def add_acc_to_feagi_data(accelerator_list, message_to_feagi):
#     return pns.append_sensory_data_for_feagi('accelerator', accelerator_list, message_to_feagi)
#
#
# def add_encoder_to_feagi_data(encoder_list, message_to_feagi):
#     return pns.append_sensory_data_for_feagi('encoder_data', encoder_list, message_to_feagi)
#
#
# def add_sound_to_feagi_data(hear_list, message_to_feagi):
#     return pns.append_sensory_data_for_feagi('hearing', hear_list, message_to_feagi)


def add_generic_input_to_feagi_data(generic_list, message_to_feagi):
    message_to_feagi['created_at'] = time.time()
    return pns.append_sensory_data_for_feagi('generic_ipu', generic_list, message_to_feagi)


def add_agent_status(status, message_to_feagi, agent_settings):
    if "data" not in message_to_feagi:
        message_to_feagi["data"] = {}
    if status:
        message_to_feagi["data"]['connected_agents'] = [agent_settings['agent_id']]
    else:
        message_to_feagi["data"]['connected_agents'] = []
    return message_to_feagi


def convert_sensor_to_ipu_data(min_output, max_output, raw_data, device_id, cortical_id='iaqpio', symmetric=False):
    if pns.full_list_dimension:
        if cortical_id in pns.full_list_dimension:
            max_input = pns.full_list_dimension[cortical_id]['cortical_dimensions'][2] - 1
            total_range = max_output - min_output
            if not symmetric:
                current_position = (raw_data / total_range) * max_input
            else:
                current_position = pns.get_map_value(raw_data, min_output, max_output, 0, max_input)
            data = str(device_id) + '-0-' + str(int(round(current_position)))
            return data
    return None


def measuring_max_and_min_range(current_data, device_id, max_value_list, min_value_list):
    """
    This function is useful if you don't know the range of maximum and minimum values for a sensor.
    It will measure and update the maximum and minimum values over time.
    """
    if device_id < len(max_value_list):
        if not max_value_list[device_id]:
            max_value_list.append(1)
            min_value_list.append(0)
    else:
        max_value_list.append(1)
        min_value_list.append(0)
    if current_data > max_value_list[device_id]:
        max_value_list[device_id] = current_data
    if current_data < min_value_list[device_id]:
        min_value_list[device_id] = current_data
    return max_value_list, min_value_list


def convert_ir_to_ipu_data(obtain_ir_list_from_robot, count, message_to_feagi):
    """
    The data from obtain_ir_list_from_robot should look something like this: [0, 1, 2], as it indicates
    which sensors are on. This will be followed by i_iinf to see which sensors are not on, using the IR count in your
    configuration.json
    """
    active_ir_indexes = {'i__inf': {}}
    inverse_ir_indexes = {'i_iinf': {}}
    for index in range(count):
        position = f"{index}-0-0"
        if index in obtain_ir_list_from_robot:
            active_ir_indexes['i__inf'][position] = 100
        else:
            inverse_ir_indexes['i_iinf'][position] = 100
    message_to_feagi = add_generic_input_to_feagi_data(active_ir_indexes, message_to_feagi)
    message_to_feagi = add_generic_input_to_feagi_data(inverse_ir_indexes, message_to_feagi)
    return message_to_feagi


def create_data_for_feagi(cortical_id='', robot_data=[], maximum_range=[], minimum_range=[], enable_symmetric=False, coumns=[], message_to_feagi={}, has_range=False):

    create_data_list = dict()
    create_data_list[cortical_id] = dict()
    start_point = coumns[0]

    for device_id in range(coumns[0], coumns[1]):
        increment = device_id - start_point
        if not has_range:
            maximum_range, minimum_range = (measuring_max_and_min_range(robot_data[increment],
                                                                        increment,
                                                                        maximum_range,
                                                                        minimum_range))
        try:
            position_of_analog = convert_sensor_to_ipu_data(
                minimum_range[increment],
                maximum_range[increment],
                robot_data[increment],
                device_id,
                cortical_id=cortical_id,
                symmetric=enable_symmetric)
            create_data_list[cortical_id][position_of_analog] = 100
        except Exception as e:
            pass
            # print(f"Caught an unexpected exception: {e}")
            # print(f"Exception type: {type(e).__name__}")
            # traceback.print_exc()
            # print("increment: ", increment, " and robot data: ", robot_data)
    if create_data_list[cortical_id]:
        message_to_feagi = add_generic_input_to_feagi_data(create_data_list, message_to_feagi)
        return message_to_feagi, maximum_range, minimum_range
    else:
        return message_to_feagi, maximum_range, minimum_range


def convert_xyz_to_012(old_dictionary_data):
    """
    This will convert from {{'x': 0, 'y': 24, 'z':32}{'x':3, 'y':39, 'z':2}} to {0:0, 1:24, 2:32, 3:3, 4:39, 5:2}}
    """
    new_dictionary_data = dict()
    increment = 0
    for key in old_dictionary_data:
        for nested_key in old_dictionary_data[key]:
            new_dictionary_data[increment] = old_dictionary_data[key][nested_key]
            increment += 1
    return new_dictionary_data

