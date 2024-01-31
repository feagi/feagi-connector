from time import sleep
import time
import threading
from configuration import *
from feagi_agent import feagi_interface as feagi
from feagi_agent import pns_gateway as pns
from feagi_agent.version import __version__
from feagi_agent import actuators
import raspberry_PI_library as rpi


def action(obtained_data):
    recieve_gpio_data = actuators.get_gpio_data(obtained_data)
    if recieve_gpio_data:
        for i in recieve_gpio_data:
            rpi.power_pin(i)
    else:
        rpi.depower_pin()


if __name__ == "__main__":
    print("Waiting on FEAGI...")

    runtime_data = {
        "current_burst_id": 0,
        "feagi_state": None,
        "cortical_list": (),
        "battery_charge_level": 1,
        "host_network": {},
        'motor_status': {},
        'servo_status': {}
    }

    # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # - - - - - - - - - - - - - - - - - - #
    feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
        feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                               __version__)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    feagi_settings['feagi_burst_speed'] = float(runtime_data["feagi_state"]['burst_duration'])
    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()

    while True:
        try:
            message_from_feagi = pns.message_from_feagi
            if message_from_feagi:
                # Fetch data such as motor, servo, etc and pass to a function (you make ur own action.
                pns.check_genome_status_no_vision(message_from_feagi)
                feagi_settings['feagi_burst_speed'] = pns.check_refresh_rate(message_from_feagi,
                                                                             feagi_settings[
                                                                                 'feagi_burst_speed'])
                obtained_signals = pns.obtain_opu_data(message_from_feagi)
                action(obtained_signals)
            sleep(feagi_settings['feagi_burst_speed'])
        except KeyboardInterrupt:
            rpi.clear_gpio()

