import socket
import time

OnBuffer = bytearray(b'\x55\x55\x80\xb0\x19\xc0\x00\x0c\x22\x00\x00\x00\x00\x04\x00\x01\x30\xff\x00\xff\xe5\x48')

# Protocol
# \x55 \x55 : Header
# \x80 \xb0
# \x04
# \xc0\x00\x0c\x22\x00\x00\x00\x00\x04\x00\x01\x30\xff\x00\xff\
# \xe5 \x48 : CRC16


OffBuffer = bytearray(b'\x55\x55\x80\xb0\x05\xc0\x00\x0c\x22\x00\x00\x00\x00\x04\x00\x01\x20\xff\x00\xff\xec\x44')

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


sock = socket.socket()
addr = socket.getaddrinfo("192.168.1.115", 9200)[0][-1]
sock.connect(addr)

print("Starting...")
sock.send(OnBuffer)
time.sleep_ms(3000)
sock.send(OffBuffer)


while True:
    data = sock.readinto(OnBuffer)
    print('.', end='')
    if data is not None:
        print("R:", Buffer)