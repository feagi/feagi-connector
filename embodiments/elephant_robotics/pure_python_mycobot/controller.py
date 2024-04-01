from pymycobot.mycobot import MyCobot
from feagi_agent import feagi_interface as FEAGI
from feagi_agent import retina as retina
from datetime import datetime
import json
import os
from time import sleep
from collections import deque

previous_data_frame = dict()


class Arm:
    @staticmethod
    def connection_initialize(port='/dev/ttyUSB0'):
        """
        :param port: The default would be '/dev/ttyUSB0'. If the port is different, put a different port.
        :return:
        """
        print("here: ", port)
        return MyCobot(port, 115200)

    # @staticmethod
    # def initialize(arm, count):
    #     default = [2048, 2048, 2048, 2048, 2048, 2048]
    #     arm.set_encoders(default, 100)
    #     for number_id in range(1, count + 1, 1):
    #         arm.get_encoder(2048)
    #     time.sleep(1)

    # @staticmethod
    # def get_coordination(robot):
    #     """
    #     :return: 6 servos' coordination
    #     """
    #     data = robot.get_coords()
    #     return data

    @staticmethod
    def power_convert(encoder_id, power):
        if encoder_id % 2 == 0:
            return -1 * power
        else:
            return abs(power)

    @staticmethod
    def encoder_converter(encoder_id):
        """
        This will convert from godot to motor's id. Let's say, you have 8x10 (width x depth from static_genome).
        So, you click 4 to go forward. It will be like this:
        o__mot': {'1-0-9': 1, '5-0-9': 1, '3-0-9': 1, '7-0-9': 1}
        which is 1,3,5,7. So this code will convert from 1,3,5,7 to 0,1,2,3 on motor id.
        Since 0-1 is motor 1, 2-3 is motor 2 and so on. In this case, 0 is for forward and 1 is for backward.
        """
        if encoder_id <= 1:
            return 1
        elif encoder_id <= 3:
            return 2
        elif encoder_id <= 5:
            return 3
        elif encoder_id <= 7:
            return 4
        elif encoder_id <= 9:
            return 5
        elif encoder_id <= 11:
            return 6
        else:
            print("Input has been refused. Please put encoder ID.")


def updating_encoder_position_in_bg():
    global runtime_data, capabilities, feagi_settings
    for i in range(1, capabilities['servo']['count'], 1):
        runtime_data['actual_encoder_position'][i] = deque([0, 0, 0, 0, 0])
    while True:
        for i in range(1, capabilities['servo']['count'], 1):
            if i != 2:
                new_data = arm.get_encoder(i)
                if new_data != -1:
                    if runtime_data['actual_encoder_position'][i]:
                        runtime_data['actual_encoder_position'][i].append(new_data)
                        runtime_data['actual_encoder_position'][i].popleft()
        print(runtime_data['actual_encoder_position'])
        # sleep(feagi_settings['feagi_burst_speed'])
        sleep(1)

def move(arm, encoder_id, power):
    if encoder_id not in runtime_data['servo_status']:
        runtime_data['servo_status'][encoder_id] = power
    max_range = capabilities['servo']['servo_range'][str(encoder_id)][1]
    min_range = capabilities['servo']['servo_range'][str(encoder_id)][0]
    if max_range >= power >= min_range:
        arm.set_encoder(encoder_id, power)


runtime_data = {
    "current_burst_id": 0,
    "feagi_state": None,
    "cortical_list": (),
    "battery_charge_level": 1,
    "host_network": {},
    'motor_status': {},
    'servo_status': {},
    'actual_encoder_position': {},
}

# NEW JSON UPDATE
f = open('configuration.json')
configuration = json.load(f)
feagi_settings = configuration["feagi_settings"]
agent_settings = configuration['agent_settings']
capabilities = configuration['capabilities']
feagi_settings['feagi_host'] = os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1")
feagi_settings['feagi_api_port'] = os.environ.get('FEAGI_API_PORT', "8000")
f.close()
message_to_feagi = {"data": {}}
# END JSON UPDATE


mycobot = Arm()
arm = mycobot.connection_initialize()
# default = [2048, 2048, 2048, 2048, 2048, 2048]
# arm.set_encoders(default, 100)
# print("version: ", arm.get_system_version())
# print("list of encoders here: ", arm.get_encoders())
# print("list of angles here: ", arm.get_angles())
arm.release_servo(1)
# print("IS CONTROLLER CONNECTED?: ", arm.is_controller_connected())
# print("is all servo enabled", arm.is_all_servo_enable())

updating_encoder_position_in_bg()
# move(arm, 2, 3000)
# sleep(5)
# move(arm, 2, 1000)
# sleep(2)

arm.release_all_servos()
