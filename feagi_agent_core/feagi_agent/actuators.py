#!/usr/bin/env python3
from feagi_agent import feagi_interface as feagi
from feagi_agent import pns_gateway as pns


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
        return power_maximum * (feagi_power/100)
    else:
        return (feagi_power / z_depth) * power_maximum
