from network import LoRa
import socket

import binascii
import struct

import ustruct
#import ubinascii

import time
import config

import machine
from machine import UART

import pycom

import json
from machine import Pin
pycom.heartbeat(False)

arduinoUART = machine.UART(1, baudrate=9600, pins=('P20','P21'))

LORA_FREQUENCY = 903900000
LORA_NODE_DR = 1

lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.US915, adr=False)

dev_addr = struct.unpack(">l", binascii.unhexlify('26021AED'))[0]
nwk_swkey = binascii.unhexlify('8B4852CFCEACFD09AFDC71FCAEF7C360')
app_swkey = binascii.unhexlify('CF314217B74704330EA8393C1AC325F7')

# remove all the non-default channels
for i in range(0, 72):  # Australia
    lora.remove_channel(i)

# set the 3 default channels to the same frequency
lora.add_channel(0, frequency=LORA_FREQUENCY, dr_min=0, dr_max=4)
lora.add_channel(1, frequency=LORA_FREQUENCY, dr_min=0, dr_max=4)
lora.add_channel(2, frequency=LORA_FREQUENCY, dr_min=0, dr_max=4)

# join a network using ABP (Activation By Personalization)
lora.join(activation=LoRa.ABP, auth=(dev_addr, nwk_swkey, app_swkey))

# create a LoRa socket
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

# set the LoRaWAN data rate
s.setsockopt(socket.SOL_LORA, socket.SO_DR, LORA_NODE_DR)

# make the socket blocking
#   True -> means we will wait for data to be sent
#s.setblocking(True)
s.setblocking(False)

'''
for i in range (200):
    pycom.rgbled(0x100000);
    pkt = b'PKT #' + bytes([i])
    print('Sending:', pkt)
    s.send(pkt)
    time.sleep(4)
    pycom.rgbled(0x001008)
    rx, port = s.recvfrom(256)
    if rx:
        print('Received: {}, on port: {}'.format(rx, port))
    time.sleep(6)
'''

# 32 BYTES
#                   12345678901234567890123456789012345678
seesawDataFormat = 'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'

def uploadData(data):
    print('Uploading Data over LoRa')
    pycom.rgbled(0x001003)

    #spliced = [data[i] for i in (0, 10, 11, 12, 13, 14, 15, 16, 17)]
    spliced = [data[i] for i in range(len(data))] # Send all
    #print('Sending>',end='',flush=True)
    #for i_data in spliced:
    #    print(i_data,end='',flush=True)
    #    s.send(bytes(i_data))
    #print(bytes(tuple(spliced)),end='',flush=True)
    s.setblocking(True)
    try:
        s.send(bytes(tuple(spliced)))
    except OSError:
        print('Operation Failed...')
    s.setblocking(False)

    #print('')
    pycom.rgbled(0x001003)
    time.sleep(0.10);

# To read seesaw:
#   issue start command (0xF0)
#   send address (I2C of seesaw)
#   send command (get data command = 0xA0)
def readSeesaws(currentSeesaw):
    success = False
    #print('Requesting Info From Arduino')
    # START COMMAND
    arduinoUART.write(bytes([0xF0]))
    # ADDRESS
    arduinoUART.write(bytes([0x10 + currentSeesaw]))
    # COMMAND
    arduinoUART.write(bytes([0xA0]))
    print('Request sent to arduino')
    time.sleep(1)
    while arduinoUART.any() >= ustruct.calcsize(seesawDataFormat):
        sawBuf = arduinoUART.readline()

        if not sawBuf:
            print('No data received')
        else:
            #print('sawBuf:', sawBuf)

            #resultBuf = ustruct.unpack('BHffbb', binascii.unhexlify(sawBuf))
            try:
                data = struct.unpack(seesawDataFormat, sawBuf)# binascii.unhexlify(sawBuf)
                #print('Result:', data)
                uploadData(sawBuf);
                success = True
            except ValueError:
                print('Incomplete Data...')
                # Attempt to clear buffer?
                arduinoUART.readall()
    #print('SUCCESS?', success)
    return success

# Test Transmissions (Send and Receive)
'''
while(True):
    s.setblocking(True)
    s.send(bytes([0x23]))
    s.setblocking(False)
    print(s.recv(64))
    time.sleep(1)
'''

currentSeesaw = 0
while(True):
    pycom.rgbled(0x100000)
    msg = s.recv(64)
    if(msg != b''):
        print('Gateway says: ',msg)
        arduinoUART.write(msg)

    if readSeesaws(currentSeesaw):
        currentSeesaw = currentSeesaw + 1
        if currentSeesaw > 5:
            currentSeesaw = 0
    time.sleep(6)
    pycom.rgbled(0x000020)
    # About 7 seconds of delay per upload
    #   Keeps us from exceeding 5000/hr variable upload rate limit
    #   that is imposed by the Tago.io website
    # Tago.io also has 500,000 variable limit... this means that
    #   at this max rate we could hold 100 hours
    # Lets extend the range of time we can have:
    #   Want a month of data: 30*24 = 720 hours
    # So the delay needs to be increased 7 times!
    #   This is only 1 upload of a single seesaw per 49 seconds
    #   Takes several minutes to update just the 6 seesaws!
    # WARNING: LoRaWAN waits for a transmission from this to send us any downstream data
    #   ---- THIS DELAY IS ALSO DELAYING DOWNSTREAM COMMANDS!
    #       So each downstream command will be delayed a minute!
    time.sleep(42) # Slow rate so tago.io will hold a month's worth of data

    # For testing, lets use a doubled delay, instead of 7x:
    #time.sleep(7)
