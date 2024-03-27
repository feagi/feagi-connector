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
import threading
import godot_bridge_functions as bridge
import feagi_connector.pns_gateway as pns
from version import __version__
from time import sleep
import feagi_connector.feagi_interface as feagi
from configuration import *
from network_configuration import *

runtime_data = {
    "cortical_data": {},
    "current_burst_id": None,
    "stimulation_period": 0.01,
    "feagi_state": None,
    "feagi_network": None,
    "cortical_list": set(),
    "host_network": {},
    "genome_number": 0,
    "old_cortical_data": {}
}


def main(feagi_settings, runtime_data, capabilities):
    """
    Main script for bridge to communicate with FEAGI and Godot.
    """
    previous_genome_timestamp = 0
    print(
        "================================ @@@@@@@@@@@@@@@ "
        "==========================================\n" * 3)
    print(
        "================================  Godot  Bridge  "
        "==========================================")
    print(
        "================================ @@@@@@@@@@@@@@@ "
        "==========================================\n" * 3)

    # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
    feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
        feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                               __version__, True)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    godot_list = {}  # initialized the list from Godot

    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()

    # This does not use PNS's websocket starter due to fundamental design differences between the
    # bridge and controllers.
    while True:
        one_frame = pns.message_from_feagi
        if one_frame != {}:
            pns.check_genome_status_no_vision(one_frame)
            if one_frame["genome_changed"] != previous_genome_timestamp:
                previous_genome_timestamp = one_frame["genome_changed"]
                if one_frame["genome_changed"] is not None:
                    print("updated time")
                    send_to_BV_queue.append("updated")
            runtime_data["stimulation_period"] = one_frame['burst_frequency']

            # processed_one_frame is the data from godot. It break down due to absolutely and
            # relatively coordination
            processed_one_frame = bridge.feagi_breakdown(one_frame)
            send_to_BV_queue.append(processed_one_frame)
        # If queue_of_recieve_godot_data has a data, it will obtain the latest then pop it for
        # the next data.
        if queue_of_recieve_godot_data:
            obtained_data_from_godot = queue_of_recieve_godot_data[0].decode('UTF-8')  # Do we
            # need it still??
            queue_of_recieve_godot_data.pop()
        else:
            obtained_data_from_godot = "{}"

        # BV wil send "ping" string so when it happens, the data will be replaced to {} for feagi
        # to not doing anything. Bridge will return the "ping" for BV to do the calculation of
        # latency.
        if obtained_data_from_godot == "ping":
            obtained_data_from_godot = "{}"
            send_to_BV_queue.append("ping")

        # Godot will send 4 of those. 3.5 or 4.0. Even if we are out of 3.5 fully, there is a
        # good chance that one of those might be occur. the usual data would be "{}" from godot.
        invalid_values = {"None", "{}", "refresh", "[]"}
        if obtained_data_from_godot not in invalid_values and obtained_data_from_godot != godot_list:
            godot_list = bridge.godot_data(obtained_data_from_godot)
            converted_data = bridge.convet_godot_coord_to_feagi_coord(
                stimulation_from_godot=godot_list,
                cortical_data_list=pns.full_list_dimension)
            print("raw data from godot:", godot_list)
            print(">>> > > > >> > converted data:", converted_data)
            if converted_data != {}:
                pns.signals_to_feagi(converted_data, feagi_ipu_channel, agent_settings)

        sleep(runtime_data["stimulation_period"])
        godot_list = {}


if __name__ == "__main__":
    threading.Thread(target=websocket_operation, args=(agent_settings,), daemon=True).start()
    threading.Thread(target=bridge_operation, args=(runtime_data,), daemon=True).start()
    # threading.Thread(target=feagi_to_brain_visualizer, args=(runtime_data,), daemon=True).start()
    while True:
        FEAGI_FLAG = False
        while not FEAGI_FLAG:
            print("entered")
            FEAGI_FLAG = feagi.is_FEAGI_reachable(
                os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1"),
                int(os.environ.get('FEAGI_OPU_PORT', "3000")))
            sleep(2)
        main(feagi_settings, runtime_data, capabilities)
