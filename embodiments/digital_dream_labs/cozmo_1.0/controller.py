#!/usr/bin/env python
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

import time
from PIL import Image
import pycozmo
from feagi_agent import feagi_interface as FEAGI
from feagi_agent import retina as retina
from feagi_agent import pns_gateway as pns
from feagi_agent import PIL_retina as pitina
from feagi_agent import sensors
from configuration import *
from typing import Optional, List
from version import __version__
import facial_expression
import requests
import sys
import os
import threading
import asyncio
from datetime import datetime
from collections import deque
import numpy as np
from time import sleep
import traceback
import math
import motor_functions

runtime_data = {
    "current_burst_id": 0,
    "feagi_state": None,
    "cortical_list": (),
    "battery_charge_level": 1,
    "host_network": {},
    'motor_status': {},
    'servo_status': {}
}

previous_frame_data = {}
robot = {'accelerator': [], "ultrasonic": [], "gyro": [], 'servo_head': [], "battery": [],
         'lift_height': []}
camera_data = {"vision": {}}


def window_average(sequence):
    return sum(sequence) // len(sequence)


def on_robot_state(cli, pkt: pycozmo.protocol_encoder.RobotState):
    """
    timestamp: The timestamp associated with the robot state.
    pose_frame_id: The ID of the frame of reference for the robot's pose.
    pose_origin_id: The ID of the origin for the robot's pose.
    pose_x, pose_y, pose_z: The x, y, and z coordinates of the robot's pose.
    pose_angle_rad: The angle of the robot's pose in radians.
    pose_pitch_rad: The pitch angle of the robot's pose in radians.
    lwheel_speed_mmps: Speed of the left wheel in millimeters per second.
    rwheel_speed_mmps: Speed of the right wheel in millimeters per second.
    head_angle_rad: The angle of the robot's head in radians.
    lift_height_mm: The height of the lift in millimeters.
    accel_x, accel_y, accel_z: Acceleration values along the x, y, and z axes.
    gyro_x, gyro_y, gyro_z: Gyroscopic values along the x, y, and z axes.
    battery_voltage: The voltage of the robot's battery.
    status: A status code associated with the robot.
    cliff_data_raw: Raw data related to cliff sensors.
    backpack_touch_sensor_raw: Raw data from the robot's backpack touch sensor.
    curr_path_segment: The ID of the current path segment.
    """
    robot['accelerator'] = {"0": pkt.accel_x - 1000, "1": pkt.accel_y - 1000,
                            "2": pkt.accel_z - 1000}
    robot['ultrasonic'] = pkt.cliff_data_raw
    robot["gyro"] = [pkt.gyro_x, pkt.gyro_y, pkt.gyro_z]
    robot['servo_head'] = pkt.head_angle_rad
    robot['battery'] = pkt.battery_voltage
    robot['lift_height'] = pkt.lift_height_mm


async def expressions():
    expressions_array = [
        facial_expression.Neutral(),
        facial_expression.Excitement2(),
        facial_expression.Anger(),
        facial_expression.Sadness(),
        facial_expression.Happiness(),
        facial_expression.Surprise(),
        facial_expression.Disgust(),
        facial_expression.Fear(),
        facial_expression.Pleading(),
        facial_expression.Vulnerability(),
        facial_expression.Despair(),
        facial_expression.Guilt(),
        facial_expression.Disappointment(),
        facial_expression.Embarrassment(),
        facial_expression.Horror(),
        facial_expression.Skepticism(),
        facial_expression.Annoyance(),
        facial_expression.Fury(),
        facial_expression.Suspicion(),
        facial_expression.Rejection(),
        facial_expression.Boredom(),
        facial_expression.Tiredness(),
        facial_expression.Asleep(),
        facial_expression.Confusion(),
        facial_expression.Amazement(),
        facial_expression.Excitement()
    ]
    face_ignor_threshold = 1
    last_face_expression_time = time.time()
    while True:
        if face_selected:
            if time.time() - last_face_expression_time > face_ignor_threshold:
                last_face_expression_time = time.time()
                face_generator = pycozmo.procedural_face.interpolate(
                    facial_expression.Neutral(), expressions_array[face_selected[0]],
                    pycozmo.robot.FRAME_RATE * 2)
                for face in face_generator:
                    # expressions_array[0].eyes[0].lids[1].y -= 0.1
                    # expressions_array[0].eyes[0].lids[1].bend -= 0.1
                    # expressions_array[0].eyes[0].lids[0].angle += 25.0
                    # expressions_array[0].eyes[1].upper_inner_radius_x += 1.0
                    # expressions_array[0].eyes[0].upper_inner_radius_x += 1.0
                    # expressions_array[0].eyes[0].scale_x += 1.25
                    # expressions_array[0].eyes[1].upper_outer_radius_x = 1.0
                    if eye_one_location:
                        expressions_array[0].eyes[0].center_x = eye_one_location[0][0]
                        expressions_array[0].eyes[0].center_y = eye_one_location[0][1]
                        eye_one_location.pop()
                    if eye_two_location:
                        expressions_array[0].eyes[1].center_x = eye_two_location[0][0]
                        expressions_array[0].eyes[1].center_y = eye_two_location[0][1]
                        eye_two_location.pop()
                    # Render face image.
                    im = face.render()
                    # The Cozmo protocol expects a 128x32 image, so take only the even lines.
                    np_im = np.array(im)
                    np_im2 = np_im[::2]
                    im2 = Image.fromarray(np_im2)
                    # Display face image.
                    cli.display_image(im2)
            face_selected.pop()
            print("poped")
        else:
            time.sleep(0.05)


def face_starter():
    asyncio.run(expressions())


def on_body_info(cli, pkt: pycozmo.protocol_encoder.BodyInfo):
    print("pkt: ", pkt)


def on_camera_image(cli, image):
    # Obtain the size automatically which will be needed in next line after the next line
    size = pitina.obtain_size(image)
    # Convert into ndarray based on the size it gets
    new_rgb = retina.RGB_list_to_ndarray(image.getdata(), size)
    # update astype to work well with retina and cv2
    new_rgb = retina.update_astype(new_rgb)
    if capabilities['camera']['mirror']:
        new_rgb = retina.flip_video(new_rgb)
    camera_data['vision'] = new_rgb
    time.sleep(0.01)


async def move_control(cli, feagi_settings, capabilities, rolling_window):
    motor_count = capabilities['motor']['count']
    while True:
        wheel_speeds = {"rf": 0, "rb": 0, "lf": 0, "lb": 0}
        for id in range(motor_count):
            motor_power = window_average(rolling_window[id])
            if id in [0, 1]:
                wheel_speeds["r" + ["f", "b"][id]] = float(motor_power)
            if id in [2, 3]:
                wheel_speeds["l" + ["f", "b"][id - 2]] = float(motor_power)
        rwheel_speed = wheel_speeds["rf"] - wheel_speeds["rb"]
        lwheel_speed = wheel_speeds["lf"] - wheel_speeds["lb"]
        motor_functions.drive_wheels(cli, lwheel_speed=lwheel_speed,
                                     rwheel_speed=rwheel_speed,
                                     duration=feagi_settings['feagi_burst_speed'])
        sleep(feagi_settings['feagi_burst_speed'])


def start_motor(motor, feagi_settings, capabilities, rolling_window):
    asyncio.run(move_control(motor, feagi_settings, capabilities, rolling_window))


def vision_initalization(cli):
    cli.add_handler(pycozmo.event.EvtNewRawCameraImage, on_camera_image)


def robot_status(cli):
    cli.add_handler(pycozmo.protocol_encoder.RobotState, on_robot_state)


def move_head(cli, angle, max, min):
    if min <= angle <= max:
        cli.set_head_angle(angle)  # move head
        return True
    else:
        print("reached to limit")
        return False


def lift_arms(cli, angle, max, min):
    if min <= angle <= max:
        cli.set_lift_height(angle)  # move head
        return True
    else:
        face_selected.append(4)
        return False


def action(obtained_data, arms_angle, head_angle):
    motor_count = capabilities['motor']['count']
    if 'motor_percentage' in obtained_data:
        if obtained_data['motor_percentage'] is not {}:
            for data_point in obtained_data['motor_percentage']:
                if data_point in [0, 1, 2, 3]:
                    device_power = obtained_data['motor_percentage'][data_point]
                    device_id = float(data_point)
                    if device_id not in motor_data:
                        motor_data[device_id] = dict()
                    rolling_window[device_id].append(device_power)
                    rolling_window[device_id].popleft()
    else:
        for _ in range(motor_count):
            rolling_window[_].append(0)
            rolling_window[_].popleft()
    if 'motor_position' in obtained_data:
        if obtained_data['motor_position'] is not {}:
            for data_point in obtained_data['motor_position']:
                if data_point in [0, 1, 2, 3]:
                    device_power = obtained_data['motor_position'][data_point] * capabilities[
                        'servo']['power_amount']
                    device_id = float(data_point)
                    if device_id not in motor_data:
                        motor_data[device_id] = dict()
                    rolling_window[device_id].append(device_power)
                    rolling_window[device_id].popleft()
    else:
        for _ in range(motor_count):
            rolling_window[_].append(0)
            rolling_window[_].popleft()
    if "servo_percentage" in obtained_data:
        if obtained_data['servo_percentage'] is not {}:
            for i in obtained_data['servo_percentage']:
                if i == 0:
                    test_head_angle = head_angle
                    test_head_angle += obtained_data['servo_percentage'][i] / capabilities["servo"][
                        "power_amount"]
                    if move_head(cli, test_head_angle, max, min):
                        head_angle = test_head_angle
                elif i == 1:
                    test_head_angle = head_angle
                    test_head_angle -= obtained_data['servo_percentage'][i] / capabilities["servo"][
                        "power_amount"]
                    if move_head(cli, head_angle, max, min):
                        head_angle = test_head_angle
                if i == 2:
                    test_arm_angle = arms_angle
                    test_arm_angle += obtained_data['servo_percentage'][i] / 40
                    if lift_arms(cli, test_arm_angle, max_lift, min_lift):
                        arms_angle = test_arm_angle
                elif i == 3:
                    test_arm_angle = arms_angle
                    test_arm_angle -= obtained_data['servo_percentage'][i] / 40
                    if lift_arms(cli, test_arm_angle, max_lift, min_lift):
                        arms_angle = test_arm_angle
            obtained_data['servo_percentage'].clear()
    if "servo_position" in obtained_data:
        if obtained_data['servo_position'] is not {}:
            for i in obtained_data['servo_position']:
                if i == 0:
                    test_head_angle = float(((obtained_data['servo_position'][i] / 10) * (max -
                                                                                          min)) + min)
                    if move_head(cli, test_head_angle, max, min):
                        head_angle = test_head_angle
                if i == 1:
                    test_arm_angle = int(((obtained_data['servo_position'][i] / 10) * (87.5 - 37))
                                         + 37)
                    if lift_arms(cli, test_arm_angle, max_lift, min_lift):
                        arms_angle = test_arm_angle
            obtained_data['servo_position'].clear()
    if "misc" in obtained_data:
        if obtained_data["misc"]:
            print("face: ", face_selected, " misc: ", obtained_data["misc"])
            for i in obtained_data["misc"]:
                face_selected.append(i)
        obtained_data['misc'].clear()
    return arms_angle, head_angle


if __name__ == '__main__':
    # # FEAGI REACHABLE CHECKER # #
    feagi_flag = False
    print("retrying...")
    print("Waiting on FEAGI...")
    while not feagi_flag:
        feagi_flag = FEAGI.is_FEAGI_reachable(
            os.environ.get('FEAGI_HOST_INTERNAL', feagi_settings["feagi_host"]),
            int(os.environ.get('FEAGI_OPU_PORT', "3000")))
        sleep(2)

    # # FEAGI REACHABLE CHECKER COMPLETED # #

    # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # - - - - - - - - - - - - - - - - - - #
    feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
        FEAGI.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                               __version__)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    face_selected = deque()
    eye_one_location = deque()
    eye_two_location = deque()
    motor_data = dict()
    rolling_window_len = capabilities['motor']['rolling_window_len']
    motor_count = capabilities['motor']['count']
    # Rolling windows for each motor
    rolling_window = {}
    # Initialize rolling window for each motor
    for motor_id in range(motor_count):
        rolling_window[motor_id] = deque([0] * rolling_window_len)

    threading.Thread(target=face_starter, daemon=True).start()
    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
    msg_counter = 0
    rgb = {'camera': {}}
    genome_tracker = 0
    # Raise head.
    cli = pycozmo.Client()
    cli.start()
    cli.connect()
    cli.wait_for_robot()
    # print("max in rad: ", pycozmo.robot.MAX_HEAD_ANGLE.radians)  # 0.7766715171374767
    # print("min in rad: ", pycozmo.robot.MIN_HEAD_ANGLE.radians)  # -0.4363323129985824
    max = pycozmo.robot.MAX_HEAD_ANGLE.radians - 0.1
    min = pycozmo.robot.MIN_HEAD_ANGLE.radians + 0.1
    max_lift = pycozmo.MAX_LIFT_HEIGHT.mm - 5
    min_lift = pycozmo.MIN_LIFT_HEIGHT.mm + 5
    threading.Thread(target=start_motor, args=(cli, feagi_settings,
                                               capabilities,
                                               rolling_window,), daemon=True).start()
    angle_of_head = \
        (pycozmo.robot.MAX_HEAD_ANGLE.radians - pycozmo.robot.MIN_HEAD_ANGLE.radians) / 2.0
    angle_of_arms = 50  # TODO: How to obtain the arms encoders in real time
    cli.set_head_angle(angle_of_head)  # move head
    lwheel_speed = 0  # Speed in millimeters per second for the left wheel
    rwheel_speed = 0  # Speed in millimeters per second for the right wheel
    lwheel_acc = 0  # Acceleration in millimeters per second squared for the left wheel
    rwheel_acc = 0  # Acceleration in millimeters per second squared for the right wheel
    duration = 0  # Duration in seconds for how long to drive the wheels

    # vision capture
    cli.enable_camera(enable=True, color=True)
    default_capabilities = {}  # It will be generated in update_region_split_downsize. See the
    # overwrite manual
    default_capabilities = pns.create_runtime_default_list(default_capabilities, capabilities)
    threading.Thread(target=robot_status, args=(cli,), daemon=True).start()
    threading.Thread(target=vision_initalization, args=(cli,), daemon=True).start()
    threading.Thread(target=retina.vision_progress,
                     args=(default_capabilities, feagi_opu_channel, api_address, feagi_settings,
                           camera_data['vision'],), daemon=True).start()
    response = requests.get(api_address + '/v1/feagi/genome/cortical_area/geometry')
    size_list = retina.obtain_cortical_vision_size(capabilities['camera']["index"], response)
    time.sleep(2)
    # vision ends
    device_list = pns.generate_OPU_list(capabilities)  # get the OPU sensors

    while True:
        try:
            message_from_feagi = pns.message_from_feagi
            if message_from_feagi['opu_data']['o_mper']:
                print(message_from_feagi['opu_data']['o_mper'])
            obtained_signals = pns.obtain_opu_data(message_from_feagi)
            angle_of_arms, angle_of_head = action(obtained_signals, angle_of_arms,
                                                  angle_of_head)
            # OPU section ENDS
            if "o_misc" in message_from_feagi["opu_data"]:
                if message_from_feagi["opu_data"]["o_misc"]:
                    print("misc: ", message_from_feagi["opu_data"]["o_misc"])
            if "o_eye1" in message_from_feagi["opu_data"]:
                if message_from_feagi["opu_data"]["o_eye1"]:
                    for i in message_from_feagi["opu_data"]["o_eye1"]:
                        split_data = i.split("-")
                        y_array = [70, 40, -60]
                        if split_data[0] == '2':
                            eye_one_location.append([80, y_array[int(split_data[1])]])
                        if split_data[0] == '1':
                            eye_one_location.append([0, y_array[int(split_data[1])]])
                        if split_data[0] == '0':
                            eye_one_location.append([-30, y_array[int(split_data[1])]])
                    face_selected.append(0)
            if "o_eye2" in message_from_feagi["opu_data"]:
                if message_from_feagi["opu_data"]["o_eye2"]:
                    for i in message_from_feagi["opu_data"]["o_eye2"]:
                        split_data = i.split("-")
                        y_array = [65, 40, -50]
                        if split_data[0] == '2':
                            eye_two_location.append([40, y_array[int(split_data[1])]])
                        if split_data[0] == '1':
                            eye_two_location.append([-10, y_array[int(split_data[1])]])
                        if split_data[0] == '0':
                            eye_two_location.append([-30, y_array[int(split_data[1])]])
                    if len(face_selected) == 0:
                        face_selected.append(0)
            if "o_init" in message_from_feagi["opu_data"]:
                if message_from_feagi["opu_data"]["o_init"]:
                    for i in message_from_feagi["opu_data"]["o_init"]:
                        split_data = i.split("-")
                        if split_data[0] == '0':
                            motor_functions.display_lines(cli)
            raw_frame = camera_data['vision']
            # # cv2.imshow("test", new_rgb)
            # # cv2.waitKey(30)
            default_capabilities['camera']['blink'] = []
            if 'camera' in default_capabilities:
                if default_capabilities['camera']['blink'] != []:
                    raw_frame = default_capabilities['camera']['blink']
            previous_frame_data, rgb, default_capabilities, size_list = retina.update_region_split_downsize(
                raw_frame,
                default_capabilities,
                size_list,
                previous_frame_data,
                rgb, capabilities)
            message_to_feagi = pns.generate_feagi_data(rgb, msg_counter, datetime.now(),
                                                       message_to_feagi)
            # print(default_capabilities['camera']['gaze_control'][0])
            sleep(feagi_settings['feagi_burst_speed'])  # bottleneck
            pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings)
            message_to_feagi.clear()
            battery = robot['battery']
            ultrasonic_data = robot['ultrasonic'][0]  # obtain ultrasonic data
            message_to_feagi = sensors.add_ultrasonic_to_feagi_data(ultrasonic_data,
                                                                    message_to_feagi)
            message_to_feagi = sensors.add_acc_to_feagi_data(robot['accelerator'],
                                                             message_to_feagi)
            message_to_feagi = sensors.add_battery_to_feagi_data(battery, message_to_feagi)

            for i in rgb['camera']:
                rgb['camera'][i].clear()
        except Exception as e:
            print("ERROR: ", e)
            traceback.print_exc()
            break
