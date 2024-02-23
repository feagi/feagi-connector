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
    echo "All scripts terminated"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Load javascript webcam if Webcam_flag is true
if [[ "$Webcam_flag" == "true" ]]; then
    python3 neuraville/javascript_webcam/controller.py &
    PID1=$!
    echo "PID of the webcam: $PID1"
fi

# Load microbit if Microbit_flag is true
if [[ "$Microbit_flag" == "true" ]]; then
    python3 elecfreaks/cutebot/web_html_microbit/controller.py &
    PID2=$!
    echo "PID of the microbit: $PID2"
fi

# Load microbit if Microbit_flag is true
if [[ "$godot_games_flag" == "true" ]]; then
    python3 godot-games-controller/controller.py &
    PID3=$!
    echo "PID of the godot games: $PID3"
fi

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

cleanup
