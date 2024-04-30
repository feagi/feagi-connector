FROM neuraville/bridge-godot-base


RUN pip3 install -U feagi_connector
COPY configuration.json /root/src/
COPY bridge_godot_python.py /root/src/
COPY version.py /root/src/

WORKDIR /root/src
CMD ["python3", "bridge_godot_python.py"]
