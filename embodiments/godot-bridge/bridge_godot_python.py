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
import asyncio
import threading
import zlib
import godot_bridge_functions as bridge
import feagi_agent.pns_gateway as pns
from version import __version__
from time import sleep
from collections import deque
import websockets
import feagi_agent.feagi_interface as feagi
from configuration import *

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


async def echo(websocket):
    """
    Main thread for websocket only.
    """
    if not current_websocket_address:
        current_websocket_address.append(websocket)
    else:
        current_websocket_address[0] = websocket
    while True:
        new_data = await websocket.recv()
        decompressed_data = zlib.decompress(new_data)
        queue_of_recieve_godot_data.append(decompressed_data)
        if "stimulation_period" in runtime_data:
            sleep(runtime_data["stimulation_period"])


async def bridge_to_BV():
    while True:
        if send_to_BV_queue:
            try:
                if current_websocket_address:
                    await current_websocket_address[0].send(zlib.compress(str(send_to_BV_queue[0]).encode()))
                    if "update" in send_to_BV_queue[0]:
                        send_to_BV_queue.popleft()
                    if "ping" in send_to_BV_queue:
                        send_to_BV_queue.popleft()
                    else:
                        send_to_BV_queue.pop()
            except Exception as error:
                sleep(0.001)
        else:
            sleep(0.001)


async def websocket_main():
    """
    This function sets up a WebSocket server using the 'websockets' library to communicate with a
    Godot game engine.

    The function establishes a WebSocket connection with a Godot game engine running on the
    specified IP address and port provided in 'agent_settings'. It uses the 'echo' coroutine to
    handle incoming WebSocket messages, which will echo back the received messages to the sender.

    Parameters: None

    Returns:
        None

    Raises:
        None

    Note: - The 'agent_settings' dictionary should contain the following keys: -
    'godot_websocket_ip': The IP address where websocket will broadcast for. By default,
    it should be "0.0.0.0".
    'godot_websocket_port': The port is by default to 9050. You can update in configuration.

        - The WebSocket server is configured with the following options: - 'max_size': The
        maximum size (in bytes) of incoming WebSocket messages. Set to 'None' for no limit. -
        'max_queue': The maximum number of incoming WebSocket messages that can be queued for
        processing. Set to 'None' for no limit. - 'write_limit': The maximum rate (in bytes per
        second) at which outgoing WebSocket messages can be sent. Set to 'None' for no limit. -
        'compression': The compression method to use for outgoing WebSocket messages. Set to
        'None' for no compression.

        - The function uses 'asyncio.Future()' to keep the WebSocket server running indefinitely.
        This is required because the 'websockets.serve()' coroutine itself does not naturally
        keep the server running; it only sets up the server to accept incoming connections and
        requires another coroutine or task to run the event loop.

    """
    async with websockets.serve(echo, agent_settings["godot_websocket_ip"],
                                agent_settings['godot_websocket_port'], max_size=None,
                                max_queue=None, write_limit=None):
        await asyncio.Future()


def websocket_operation():
    """
    Run asyncio using websocket operations.

    This function runs the 'websocket_main()' coroutine using asyncio's 'run' function,
    which provides a simple way to execute the coroutine in the event loop.
    """
    asyncio.run(websocket_main())


def bridge_operation():
    asyncio.run(bridge_to_BV())


def feagi_to_brain_visualizer():
    """
    Keep send_to_BV queue stay under 2 for bridge_to_BV() function. So that way, it can send latest.
    """
    while True:
        if len(send_to_BV_queue) > 0:
            if len(send_to_BV_queue) > 2:
                stored_value = send_to_BV_queue.pop()
                send_to_BV_queue.clear()
                send_to_BV_queue.append(stored_value)
        if "stimulation_period" in runtime_data:
            sleep(runtime_data["stimulation_period"])


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
    queue_of_recieve_godot_data = deque()
    send_to_BV_queue = deque()
    current_websocket_address = deque()
    threading.Thread(target=websocket_operation, daemon=True).start()
    threading.Thread(target=bridge_operation, daemon=True).start()
    threading.Thread(target=feagi_to_brain_visualizer, daemon=True).start()
    current_cortical_area = {}
    while True:
        FEAGI_FLAG = False
        print("Waiting on FEAGI...")
        while not FEAGI_FLAG:
            FEAGI_FLAG = feagi.is_FEAGI_reachable(
                os.environ.get('FEAGI_HOST_INTERNAL', "127.0.0.1"),
                int(os.environ.get('FEAGI_OPU_PORT', "3000")))
            sleep(2)
        main(feagi_settings, runtime_data, capabilities)
