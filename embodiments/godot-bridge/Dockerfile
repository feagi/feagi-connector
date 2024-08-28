FROM neuraville/bridge-godot-base

RUN apt-get update
RUN apt install -y libgl1-mesa-glx libglib2.0-0
RUN pip3 install -U feagi_connector
COPY capabilities.json /root/
COPY networking.json /root/src/
COPY bridge_godot_python.py /root/src/
COPY version.py /root/src/
COPY godot_bridge_functions.py /root/src/
COPY network_configuration.py /root/src/

WORKDIR /root/src
CMD ["python3", "bridge_godot_python.py"]
