FROM python:3.8-buster

ENV PATH="${PATH}:/sbin;/bin"
RUN apt-get update


# Python
RUN pip3 install --upgrade pip && \
    pip3 install -U feagi_connector && \
    pip3 install jinja2 && \
    pip3 install pygame && \
    pip3 install opencv-python==4.7.0.68
RUN pip3 install websockets
RUN pip3 install fastapi
RUN apt install -y libgl1-mesa-glx
RUN pip3 install lz4

ENV Running_In_CONTAINER Yes
WORKDIR /root/

COPY controller.py /root/
COPY networking.json /root/
COPY requirements.txt /root/
COPY version.py /root/
CMD ["python3", "controller.py"]
