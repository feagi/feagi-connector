from time import sleep
import time
import threading

import pyfirmata

from configuration import *
from collections import deque
from feagi_agent import feagi_interface as feagi
from feagi_agent import pns_gateway as pns
from feagi_agent.version import __version__
from feagi_agent import actuators
from feagi_agent import sensors
from pyfirmata import Arduino, SERVO, util

servo_status = dict()
motor_status = dict()
pin_board = dict()
analog_pin_board = dict()
pin_mode = dict()
rolling_window = {}
rolling_window_len = capabilities['motor']['rolling_window_len']
motor_count = capabilities['motor']['count']
output_track = list()
input_track = list()


def list_all_pins(board):
    all_pins = dict()
    for pin in board._layout['digital']:
        if pin not in [0, 1]:  # 0 and 1 are not available for output.
            all_pins[pin] = ""  # initalize empty key
    for pin in all_pins:
        current = pin  # Due to serial communcations port
        pin_board[current] = board.get_pin('d:{0}:s'.format(int(pin)))
        pin_mode[current] = 4


def list_all_analog_pins(board):
    all_pins = dict()
    for pin in board.analog:
        all_pins[pin.pin_number] = ""
    for pin in all_pins:
        analog_pin_board[pin] = board.get_pin('a:{0}:i'.format(int(pin)))
    print(analog_pin_board)


def set_pin_mode(pin, mode, id):
    pin.mode = mode
    pin_mode[id] = mode


def action(obtained_data):
    recieve_servo_data = actuators.get_servo_data(obtained_data, True)
    recieve_gpio_data = actuators.get_gpio_data(obtained_data)
    check_input_request = actuators.check_convert_gpio_to_input(obtained_data)
    if check_input_request:
        for id in check_input_request:
            if id in pin_mode:
                if pin_mode[int(id)] != 0:
                    set_pin_mode(pin_board[int(id)], 0, id)
                    input_track.append(id)
    if recieve_gpio_data:
        for i in recieve_gpio_data:
            if i in pin_mode:
                if pin_mode[int(i)] != 1:
                    set_pin_mode(pin_board[int(i)], 1, i)
                    if int(i) in input_track:
                        input_track.remove(int(i))
                pin_board[int(i)].write(1)
                output_track.append(int(i))  # Tracking whatever used digital
            else:
                print("pin: ", i, " is not configured. Select another pin please.")
    else:
        if output_track:
            pin_board[output_track[0]].write(0)
            output_track.pop()

    if recieve_servo_data:
        # Do some custom work with servo data as well
        for id in recieve_servo_data:
            if id in pin_mode:
                if pin_mode[int(id)] != 4:
                    print("reset your board to use the servo again after you updated pin: ", id)
                    set_pin_mode(pin_board[int(id)], pyfirmata.OUTPUT, id)
                servo_power = actuators.servo_generate_power(180, recieve_servo_data[id], id)
                if id in motor_status:
                    del motor_status[id]
                if id not in servo_status:
                    servo_status[id] = actuators.servo_keep_boundaries(servo_power)
                    pin_board[id].write(servo_status[id])
                else:
                    servo_status[id] += servo_power / 100
                    servo_status[id] = actuators.servo_keep_boundaries(servo_status[id])
                    pin_board[id].write(servo_status[id])
            else:
                print("pin: ", id, " is not configured. Select another pin please.")

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
    # Specify the serial port where your Arduino is connected (e.g., 'COM3' on Windows or
    # '/dev/ttyUSB0' on Linux)
    feagi_settings['feagi_burst_speed'] = float(runtime_data["feagi_state"]['burst_duration'])
    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
    port = capabilities['arduino']['port']  # Don't change this
    board = Arduino(port)
    it = util.Iterator(board)  # for Analog or Input
    it.start()
    # list_all_analog_pins(board) # Temporarily pause analog section
    time.sleep(5)
    list_all_pins(board)
    # Initialize rolling window for each motor
    for motor_id in range(motor_count):
        rolling_window[motor_id] = deque([0] * rolling_window_len)

    while True:
        message_from_feagi = pns.message_from_feagi
        if message_from_feagi:
            # Fetch data such as motor, servo, etc and pass to a function (you make ur own action.
            pns.check_genome_status_no_vision(message_from_feagi)
            feagi_settings['feagi_burst_speed'] = \
                pns.check_refresh_rate(message_from_feagi, feagi_settings['feagi_burst_speed'])
            obtained_signals = pns.obtain_opu_data(message_from_feagi)
            action(obtained_signals)
        if input_track:
            create_generic_input_dict = dict()
            create_generic_input_dict['i_gpio'] = dict()
            for pin in input_track:
                obtain_data = pin_board[pin].read()
                if obtain_data:
                    location_string = str(pin) + "-0-0"
                    create_generic_input_dict['i_gpio'][location_string] = 100
            message_to_feagi = sensors.add_generic_input_to_feagi_data(
                create_generic_input_dict, message_to_feagi)
            pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings)
        sleep(feagi_settings['feagi_burst_speed'])
