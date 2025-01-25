FROM docker.io/library/python:3.12

RUN mkdir /app
WORKDIR /app

ENV PYTHONPATH=${PYTHONPATH}:${PWD}

# copy requirements first to create better cache layers
COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY . /app/

CMD ["python", "ninjaCapeSerialMQTTBridge.py"]

