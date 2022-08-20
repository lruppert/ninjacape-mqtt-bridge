FROM docker.io/library/python:3.10

RUN mkdir /app
WORKDIR /app

ENV PYTHONPATH=${PYTHONPATH}:${PWD}
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1
RUN pip install cryptography==3.3.2

# copy requirements first to create better cache layers
COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY . /app/

CMD ["python", "ninjaCapeSerialMQTTBridge.py"]

