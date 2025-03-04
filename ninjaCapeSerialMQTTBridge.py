#!/usr/bin/env python3
#
# used to interface the NinjaCape to openHAB via MQTT
# - reads data from serial port and publishes on MQTT client
# - writes data to serial port from MQTT subscriptions
#
# - uses the Python MQTT client from the Mosquitto project
#   http://mosquitto.org (now in Paho)
#
# https://github.com/lruppert/ninjacape-mqtt-bridge
# lruppert, based on code by perrin7

import json
import threading
import time
import configparser
import serial
import paho.mqtt.client as mqtt

# Settings
DEFAULT_CONFIG = "ninjacape-mqtt-bridge.cfg"

serialdev = None
broker = None
port = None

debug = False  # set this to True for lots of prints

# buffer of data to output to the serial port
outputData = []


#
# This loads the config file defined in the default config path
#
def load_config(config_path):
    parser = configparser.RawConfigParser()
    parser.read(config_path)
    return parser


#  MQTT callbacks
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        # reason_code 0 successful connect
        print("Connected")
    else:
        print("Unable to connect. Error code %d" % reason_code)
        raise Exception
    # subscribe to the output MQTT messages
    output_mid = client.subscribe("ninjaCape/output/#")


def on_publish(client, userdata, mid, reason_codes, properties):
    if debug:
        print("Published. mid:", mid)


def on_subscribe(client, userdata, mid, reason_codes, properties):
    if debug:
        print("Subscribed. mid:", mid)


def on_message_output(client, userdata, msg):
    if debug:
        print("Output Data: ", msg.topic, "data:", msg.payload)
    # add to outputData list
    outputData.append(msg)


def on_message(client, userdata, message):
    if debug:
        print("Unhandled Message Received: ", message.topic, message.payload)


# called on exit
# close serial, disconnect MQTT
def cleanup():
    print("Ending and cleaning up")
    ser.close()
    mqttc.disconnect()


def mqtt_to_json_output(mqtt_message):
    encoded_payload = None
    topics = mqtt_message.topic.split('/')
    # JSON message in ninjaCape form
    json_data = ('{"DEVICE": [{"G":"0","V":0,"D":'
                 + topics[2]
                 + ',"DA":"'
                 + mqtt_message.payload.decode('utf8') + '"}]}')
    try:
        encoded_payload = json_data.encode()
    except UnicodeError as e:
        print("ERROR: %s (%s)" % (e.msg, json_data))
    return encoded_payload


# thread for reading serial data and publishing to MQTT client
def serial_read_and_publish(ser, mqttc):
    ser.flushInput()

    while True:
        json_data = None
        line = ser.readline()  # this is blocking
        if debug:
            print("line to decode:", line)

        # split the JSON packet up here and publish on MQTT
        try:
            json_data = json.loads(line)
        except json.JSONDecodeError as e:
            print("ERROR: %s (%s)" % (e.msg, line))

        if debug:
            print("json decoded:", json_data)

        try:
            device = str(json_data['DEVICE'][0]['D'])
            data = str(json_data['DEVICE'][0]['DA'])
            mqttc.publish("ninjaCape/input/"+device, data)
        except KeyError:
            # TODO should probably do something here if the data is malformed
            pass


# MAIN PROGRAM START
if __name__ == "__main__":
    config = load_config(DEFAULT_CONFIG)

    serialdev = config.get("serial", "device")
    broker = config.get("mqtt", "server")
    port = config.getint("mqtt", "port")
    tls = config.getboolean("mqtt", "tls")

    try:
        username = config.get("mqtt", "username")
        password = config.get("mqtt", "password")
        auth = True
    except configparser.NoOptionError:
        auth = False

    try:
        print("Connecting... ", serialdev)
        # connect to serial port
        # timeout 0 for non-blocking. Set to None for blocking.
        ser = serial.Serial(serialdev, 9600, timeout=None)
    except serial.serialutil.SerialException as serial_exception:
        print("Failed to connect serial"+str(serial_exception))
        # unable to continue with no serial input
        raise SystemExit

    try:
        # create an mqtt client
        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,"ninjaCape")

        # attach MQTT callbacks
        mqttc.on_connect = on_connect
        mqttc.on_publish = on_publish
        mqttc.on_subscribe = on_subscribe
        mqttc.on_message = on_message
        mqttc.message_callback_add("ninjaCape/output/#", on_message_output)

        if tls:
            mqttc.tls_set()
        if auth:
            mqttc.username_pw_set(username=username, password=password)

        # connect to broker
        mqttc.connect(broker, port, 60)

        # start the mqttc client thread
        mqttc.loop_start()

        serial_thread = threading.Thread(target=serial_read_and_publish,
                                         args=(ser, mqttc))
        serial_thread.daemon = True
        serial_thread.start()

        while True:  # main thread
            # writing to serial port if there is data available
            if len(outputData) > 0:
                ser.write(mqtt_to_json_output(outputData.pop()))

            time.sleep(0.5)

    # handle app closure
    except KeyboardInterrupt:
        print("Interrupt received")
        cleanup()
    except RuntimeError:
        print("uh-oh! time to die")
        cleanup()
