from time import sleep
import time
import json
import threading
from configuration import *
from feagi_agent import feagi_interface as feagi
from feagi_agent import pns_gateway as pns
from feagi_agent.version import __version__
from feagi_agent import actuators
from pyfirmata import Arduino, SERVO


def action(obtained_data):
    recieve_servo_data = actuators.get_servo_data(obtained_data)
    if recieve_servo_data:
        # Do some custom work with servo data as well
        for id in recieve_servo_data:
            print(recieve_servo_data)
            servo_power = actuators.servo_generate_power(180, recieve_servo_data[id], id)
            print("power: ", servo_power)
            servo.write(servo_power)

if __name__ == "__main__":
    # # FEAGI REACHABLE CHECKER # #
    print("retrying...")
    print("Waiting on FEAGI...")
    # while not feagi_flag:
    #     print("ip: ", os.environ.get('FEAGI_HOST_INTERNAL', feagi_settings["feagi_host"]))
    #     print("here: ", int(os.environ.get('FEAGI_OPU_PORT', "30000")))
    #     feagi_flag = feagi.is_FEAGI_reachable(
    #         os.environ.get('FEAGI_HOST_INTERNAL', feagi_settings["feagi_host"]),
    #         int(os.environ.get('FEAGI_OPU_PORT', "30000")))
    #     sleep(2)

    runtime_data = {
        "current_burst_id": 0,
        "feagi_state": None,
        "cortical_list": (),
        "battery_charge_level": 1,
        "host_network": {},
        'motor_status': {},
        'servo_status': {}
    }
    # # FEAGI REACHABLE CHECKER COMPLETED # #

    # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # - - - - - - - - - - - - - - - - - - #
    feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
        feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                               __version__)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Specify the serial port where your Arduino is connected (e.g., 'COM3' on Windows or '/dev/ttyUSB0' on Linux)
    feagi_settings['feagi_burst_speed'] = float(runtime_data["feagi_state"]['burst_duration'])
    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
    port = 'COM5'
    board = Arduino(port)
    print("inital;izing the board")
    time.sleep(5)
    servo_pin = 13
    servo = board.get_pin('d:{0}:s'.format(servo_pin))
    print(servo)
    sleep(5)
    servo.write(90)


    while True:
        message_from_feagi = pns.message_from_feagi
        if message_from_feagi:
            # Fetch data such as motor, servo, etc and pass to a function (you make ur own action.
            pns.check_genome_status_no_vision(message_from_feagi)
            feagi_settings['feagi_burst_speed'] = pns.check_refresh_rate(message_from_feagi,
                                                                         feagi_settings['feagi_burst_speed'])
            obtained_signals = pns.obtain_opu_data(message_from_feagi)
            action(obtained_signals)
        sleep(feagi_settings['feagi_burst_speed'])
