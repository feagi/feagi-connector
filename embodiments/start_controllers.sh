#!/bin/bash

# Define a cleanup function
cleanup() {
    echo "Terminating scripts"
    if [[ ! -z "$PID1" ]]; then
        kill $PID1
        echo "Webcam script terminated"
    fi
    if [[ ! -z "$PID2" ]]; then
        kill $PID2
        echo "Microbit script terminated"
    fi
        if [[ ! -z "$PID3" ]]; then
        kill $PID3
        echo "Godot games script terminated"
    fi
        if [[ ! -z "$PID4" ]]; then
        wait $PID4
    fi
    echo "All scripts terminated"
    exit 0
}

trap cleanup SIGTERM SIGINT

export FEAGI_HOST_INTERNAL=$(hostname)

cd /root/godot-bridge/
python3 bridge_godot_python.py &
cd /root/

# Load javascript webcam if WEBCAM_FLAG is true
if [[ "$WEBCAM_FLAG" == "true" ]]; then
    cd neuraville/javascript_webcam/
    python3 controller.py &
    PID1=$!
    echo "PID of the webcam: $PID1"
    cd /root/
fi

# Load microbit if MICROBIT_FLAG is true
if [[ "$MICROBIT_FLAG" == "true" ]]; then
    cd elecfreaks/cutebot/web_html_microbit/
    python3 controller.py &
    PID2=$!
    echo "PID of the microbit: $PID2"
    cd /root/
fi

# Load microbit if MICROBIT_FLAG is true
if [[ "$GODOT_GAMES_FLAG" == "true" ]]; then
    cd godot-games-controller
    python3 controller.py &
    PID3=$!
    echo "PID of the godot games: $PID3"
    cd /root/
fi

# Load microbit if MICROBIT_FLAG is true
if [[ "$WEBSOCKET_BRIDGE" == "true" ]]; then
    cd controller-bridge
    python3 controller.py &
    PID4=$!
    echo "PID of the controller-bridge: $PID4"
    cd /root/
fi

cd /opt/source-code/feagi/src/
python3 main.py

# Optionally, wait for the scripts to finish if they were started
if [[ ! -z "$PID1" ]]; then
    wait $PID1
fi

if [[ ! -z "$PID2" ]]; then
    wait $PID2
fi

if [[ ! -z "$PID3" ]]; then
    wait $PID3
fi

if [[ ! -z "$PID4" ]]; then
    wait $PID4
fi

cleanup
