from time import sleep
import time
import ardSerial
import threading
from configuration import *
from feagi_agent import feagi_interface as feagi
from feagi_agent import pns_gateway as pns
from feagi_agent.version import __version__
from feagi_agent import actuators

servo_status = dict()


def action(obtained_data):
    servo_data = actuators.get_servo_data(obtained_data, True)
    if servo_data:
        for device_id in servo_data:
            servo_power = actuators.servo_generate_power(90, servo_data[device_id], device_id)
            if device_id not in servo_status:
                servo_status[device_id] = actuators.servo_keep_boundaries(servo_power)
                # pin_board[device_id].write(servo_status[device_id])
            else:
                servo_status[device_id] += servo_power / 10
                servo_status[device_id] = actuators.servo_keep_boundaries(servo_status[device_id])
                # pin_board[device_id].write(servo_status[device_id])
                token = 8
                task = servo_status[device_id] - 90  # white space
                ardSerial.send(ardSerial.goodPorts, ['i', [token, task], 0.001])
                print("here: ", servo_status)


if __name__ == "__main__":
    ardSerial.connectPort(ardSerial.goodPorts)
    t = threading.Thread(target=ardSerial.keepCheckingPort, args=(ardSerial.goodPorts,))
    t.start()
    # ardSerial.keepReadingInput(ardSerial.goodPorts)
    print("Ready...")
    feagi_flag = False
    print("Waiting on FEAGI...")
    while not feagi_flag:
        feagi_flag = feagi.is_FEAGI_reachable(os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1"),
                                              int(os.environ.get('FEAGI_OPU_PORT', "3000")))
        sleep(2)
    print("DONE")
    previous_data_frame = {}
    runtime_data = {"cortical_data": {}, "current_burst_id": None, "stimulation_period": 0.01,
                    "feagi_state": None, "feagi_network": None}

    # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
        feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                               __version__)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    msg_counter = runtime_data["feagi_state"]['burst_counter']

    # To give ardiuno some time to open port. It's required
    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
    time.sleep(5)
    while True:
        message_from_feagi = pns.message_from_feagi

        # Fetch data such as motor, servo, etc and pass to a function (you make ur own action.
        if message_from_feagi is not None:
            pns.check_genome_status_no_vision(message_from_feagi)
            feagi_settings['feagi_burst_speed'] = \
                pns.check_refresh_rate(message_from_feagi, feagi_settings['feagi_burst_speed'])
            obtained_signals = pns.obtain_opu_data(message_from_feagi)
            action(obtained_signals)
        sleep(feagi_settings['feagi_burst_speed'])
