FROM python:3.8-buster

ENV PATH="${PATH}:/sbin;/bin"
RUN apt-get update

RUN apt-get update && \
    apt install -y libgl1-mesa-glx

RUN pip3 install --upgrade pip && \
    pip3 install -U feagi_agent && \
    pip3 install opencv-python==4.7.0.68 && \
    pip3 install websockets && \
    pip3 install fastapi && \
    pip3 install lz4


ENV Running_In_CONTAINER Yes
WORKDIR /root/

# Copy the required directories into the container at /usr/src/app
COPY neuraville/javascript_webcam/ ./neuraville/javascript_webcam/
COPY elecfreaks/cutebot/web_html_microbit/ ./elecfreaks/cutebot/web_html_microbit/
COPY godot-games-controller/ ./godot-games-controller/
COPY start_controllers.sh .

# Install any needed packages specified in requirements.txt
# Uncomment and adjust if you have requirements.txt in your directories
# RUN pip install --no-cache-dir -r ./neuraville/javascript_webcam/requirements.txt
# RUN pip install --no-cache-dir -r ./elecfreaks/cutebot/web_html_microbit/requirements.txt
# RUN pip install --no-cache-dir -r ./godot-games-controller/requirements.txt

# Make sure your script is executable
RUN chmod +x ./start_controllers.sh

# Run start_controllers.sh when the container launches
CMD ["./start_controllers.sh"]
