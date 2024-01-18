#!/usr/bin/env python3
import asyncio
from time import sleep
from collections import deque
from feagi_agent import pns_gateway as pns
from feagi_agent import feagi_interface as feagi

motor_data = dict()


def window_average(sequence):
    return sum(sequence) // len(sequence)


def obtain_opu_data(device_list, message_from_feagi):
    opu_signal_dict = {}
    opu_data = feagi.opu_processor(message_from_feagi)
    for i in device_list:
        if i in opu_data and opu_data[i]:
            for x in opu_data[i]:
                if i not in opu_signal_dict:
                    opu_signal_dict[i] = {}
                opu_signal_dict[i][x] = opu_data[i][x]
    return opu_signal_dict


def motor_generate_power(power_maximum, feagi_power):
    z_depth = pns.full_list_dimension['motor_opu'][6]
    if z_depth == 1:
        return power_maximum * (feagi_power / 100)
    else:
        return (feagi_power / z_depth) * power_maximum


def servo_generate_power(power, feagi_power, id):
    z_depth = pns.full_list_dimension['servo_opu'][6]
    if id / z_depth == 0:
        return power * (feagi_power / 100)
    else:
        return (feagi_power / z_depth) * power


def motor_converter(motor_id):
    """
    This function converts motor IDs from 1,3,5,7 to 0,1,2,3.
    """
    if motor_id % 2 == 0:
        return motor_id // 2
    else:
        return (motor_id - 1) // 2


def power_convert(motor_id, power):
    if motor_id % 2 == 0:
        return -1 * power
    else:
        return abs(power)


def get_motor_data(obtained_data, power_maximum, motor_count, moving_average, power_converter=True):
    if 'motor' in obtained_data:
        if obtained_data['motor'] is not {}:
            for data_point in obtained_data['motor']:
                device_power = obtained_data['motor'][data_point]
                device_power = int(motor_generate_power(power_maximum, device_power))
                if power_converter:
                    device_power = power_convert(data_point, device_power)
                device_id = motor_converter(data_point)
                moving_average = update_moving_average(moving_average, device_id, device_power)
    else:
        for _ in range(motor_count):
            moving_average[_].append(0)
            moving_average[_].popleft()
    motor_data = dict()
    for id in moving_average:
        motor_data[id] = window_average(moving_average[id])
    return motor_data


def update_moving_average(moving_average, device_id, device_power):
    moving_average[device_id].append(device_power)
    moving_average[device_id].popleft()
    return moving_average


def get_servo_data(obtained_data):
    servo_data = dict()
    if 'servo' in obtained_data:
        for data_point in obtained_data['servo']:
            device_id = data_point
            device_power = obtained_data['servo'][data_point]
            servo_data[device_id] = device_power
    return servo_data
