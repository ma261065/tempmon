import socket
import time
import struct

TYPE_STANDARD = const(1)
TYPE_EXTENDED = const(2)
TYPE_OTHER = const(3)

OnBuffer = bytearray(b'\x55\x55\x80\xb0\x19\xc0\x00\x0c\x22\x00\x00\x00\x00\x04\x00\x01\x30\xff\x00\xff\xe5\x48')

# Protocol
# \x55 \x55 : Header
# \x80 \xb0
# \x04
# \xc0\x00\x0c\x22\x00\x00\x00\x00\x04\x00\x01\x30\xff\x00\xff\
# \xe5 \x48 : CRC16


OffBuffer =bytearray(b'\x55\x55\x80\xb0\x05\xc0\x00\x0c\x22\x00\x00\x00\x00\x04\x00\x01\x20\xff\x00\xff\xec\x44')

Buffer = bytearray(42)

PRESET = 0xFFFF
POLYNOMIAL = 0xA001 # bit reverse of 0x8005

def crc16(data):
    crc = PRESET
    for c in data:
        crc = crc ^ c
        for j in range(8):
            if crc & 0x01:
                crc = (crc >> 1) ^ POLYNOMIAL
            else:
                crc = crc >> 1
    return crc

def parse_packet_header(data_in):
    type = None
    length = 0
    
    if data_in[0] != 0x55 and data_in[1] != 0x55:
        print("Data doesn't start with 0x55 0x55")
        return None
    
    if data_in[2] == 0x9f and data_in[3] == 0x80:
        print("Received small message")
    elif data_in[2] == 0xb0 and data_in[3] == 0x90:
        print("Received big message")

    print(f"Message ID:{data_in[4]}")
    
    if data_in[5] == 0xc0:
        msgtype = TYPE_STANDARD
        print("CONTROL_STATUS")
    elif data_in[5] == 0x1f:
        msgtype = TYPE_EXTENDED
        print("EXTENDED")
    elif data_in[5] == 0x27:
        msgtype = TYPE_OTHER
        print("OTHER")
    else:
        print("Unknown message type")
    
    length = data_in[6] * 256 + data_in[7]
    print(f"Num bytes:{length}")

    if data_in[length + 9 - 1] * 256 + data_in[length + 9] == crc16(data_in[2:length + 9 - 1]):
        print("CRC OK")
    else:
        print("Bad CRC")
        return None

    return length, msgtype, data_in[8:-2]


def TurnAirconOn(sock):
    sock.send(OnBuffer)
    
def TurnAirconOff(sock):    
    sock.send(OffBuffer)
    