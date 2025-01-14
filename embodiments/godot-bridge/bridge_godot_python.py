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
import os
import json
import threading
from datetime import datetime
from version import __version__
from network_configuration import *
import godot_bridge_functions as bridge
import feagi_connector.pns_gateway as pns
import feagi_connector.feagi_interface as feagi
import feagi_connector.retina as retina
from FEAGIByteStructures.JSONByteStructure import JSONByteStructure

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

feagi.validate_requirements('requirements.txt')  # you should get it from the boilerplate generator


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
    current_genome_number = 0
    current_register_number = 0
    timerout_setpoint = 3
    start_timer = datetime.now()
    size = [32, 32] # by default
    while True:
        # if not feagi.is_FEAGI_reachable(feagi_settings['feagi_host'], int(feagi_settings['feagi_api_port'])):
        #     break
        one_frame = pns.message_from_feagi
        processed_one_frame_dict = {
            "status": {},
            "activations": []
        }
        if one_frame != {}:
            pns.check_genome_status_no_vision(one_frame)
            if one_frame["genome_changed"] != previous_genome_timestamp:
                previous_genome_timestamp = one_frame["genome_changed"]
                if one_frame["genome_changed"] is not None:
                    if one_frame["genome_num"] != current_genome_number or one_frame['change_register'] != current_register_number:
                        print("updated time")
                        processed_one_frame_dict["status"]["genome_changed"] = True
                        current_genome_number = one_frame["genome_num"]
                        current_register_number = one_frame['change_register']['agent']
            runtime_data["stimulation_period"] = one_frame['burst_frequency']
            # processed_one_frame is the data from godot. It break down due to absolutely and
            # relatively coordination
            processed_one_frame = bridge.feagi_breakdown(one_frame)
            processed_one_frame_dict["activations"] = processed_one_frame
            processed_one_frame_dict["status"]["burst_engine"] = one_frame.get("burst_engine")
            processed_one_frame_dict["status"]["genome_availability"] = one_frame.get("genome_availability")
            processed_one_frame_dict["status"]["genome_validity"] = one_frame.get("genome_validity")
            processed_one_frame_dict["status"]["brain_readiness"] = one_frame.get("brain_readiness")
            processed_one_frame_dict['size'] = size
            if pns.full_list_dimension:
                if 'iv00CC' in pns.full_list_dimension:
                    size = list(retina.grab_xy_cortical_resolution('iv00CC'))
                    processed_one_frame_dict['rgb'] = bridge.rgb_extract(one_frame.get("color_image"), size)
            if "amalgamation_pending" in one_frame:
                processed_one_frame_dict["status"]["amalgamation_pending"] = one_frame.get("amalgamation_pending")
                if 'initiation_time' in processed_one_frame_dict["status"]["amalgamation_pending"]:
                    processed_one_frame_dict["status"]["amalgamation_pending"].pop('initiation_time')
            start_timer = datetime.now()
        elif float(timerout_setpoint) <= (datetime.now() - start_timer).total_seconds():
            processed_one_frame_dict["activations"] = {}
            processed_one_frame_dict["status"]["burst_engine"] = False
            processed_one_frame_dict["status"]["genome_availability"] = False
            processed_one_frame_dict["status"]["genome_validity"] = False
            processed_one_frame_dict["status"]["brain_readiness"] = False
        json_wrapped: JSONByteStructure = JSONByteStructure.create_from_json_string(json.dumps(processed_one_frame_dict))
        send_to_BV_queue.append(json_wrapped.to_bytes())
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
                pns.signals_to_feagi(converted_data, feagi_ipu_channel, agent_settings, feagi_settings)
        sleep(runtime_data["stimulation_period"])
        one_frame.clear()
        godot_list = {}


if __name__ == "__main__":
    # NEW JSON UPDATE
    f = open('configuration.json')
    configuration = json.load(f)
    feagi_settings = configuration["feagi_settings"]
    agent_settings = configuration['agent_settings']
    capabilities = {}  # Just to make feagi interface happy
    feagi_settings['feagi_host'] = os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1")
    feagi_settings['feagi_api_port'] = os.environ.get('FEAGI_API_PORT', "8000")
    agent_settings['godot_websocket_port'] = os.environ.get('WS_BRIDGE_PORT', "9050")
    f.close()
    message_to_feagi = {"data": {}}
    # END JSON UPDATE

    threading.Thread(target=websocket_operation, args=(agent_settings,), daemon=True).start()
    threading.Thread(target=bridge_operation, args=(runtime_data,), daemon=True).start()
    threading.Thread(target=feagi_to_brain_visualizer, args=(runtime_data,), daemon=True).start()
    while True:
        FEAGI_FLAG = False
        print("Waiting on Feagi...")
        while not FEAGI_FLAG:
            FEAGI_FLAG = feagi.is_FEAGI_reachable(
                feagi_settings['feagi_host'],
                int(feagi_settings['feagi_api_port']))
            sleep(2)
        main(feagi_settings, runtime_data, capabilities)
