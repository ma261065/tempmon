from binascii import hexlify
from bluetooth import BLE
from micropython import const
from time import localtime, sleep
from struct import unpack
from umqttsimple import MQTTClient
import machine, network, socket, ntptime, time
import asyncio
import airtouch
import webserver
import sys
import webrepl
import esp32


_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)

# Create an empty dictionary to store sensor data
sensor_data = {}
my_timer = machine.Timer(-1)

def connect_to_WiFi():
    # Get the access point and password from non-volatile storage
    nvs = esp32.NVS("keys")
    buf = bytearray(32)
    nvs.get_blob("ap", buf)
    ap = buf.rstrip(b'\x00').decode('utf-8')
    nvs.get_blob("pw", buf)
    pw = buf.rstrip(b'\x00').decode('utf-8')
    
    sta_if = network.WLAN(network.STA_IF)

    if not sta_if.isconnected():
        sta_if.active(True)
        print(f"Connecting to WiFi {ap}...")
        #mac = sta_if.config('mac')
        #host = 'esp32-' + ''.join('{:02x}'.format(b) for b in mac[3:])
        host = 'aircon'
        sta_if.config(dhcp_hostname = host)
        sta_if.connect(ap, pw)

        while not sta_if.isconnected():
            pass

    host = sta_if.config('dhcp_hostname')
    print('Wifi connected as {}/{}, net={}, gw={}, dns={}'.format(host, *sta_if.ifconfig()))

    
# Called once a minute
def timer_callback(timer):
    now = time.localtime()

    # Print the sensor data
    for sensor, info in sensor_data.items():
        print("-" * 20)
        print(f"Sensor ID: {sensor}")
        print(f"Name: {info['name']}")
        print(f"Temperature: {info['temperature']}°C")
        print(f"Humidity: {info['humidity']}%")
        print(f"Battery Level: {info['battery']}%")
        print(f"RSSI: {info['rssi']} dBm")
        print(f"Voltage: {info['voltage']}V")
        print(f"Power: {info['power']}")
        print(f"Last Updated: {info['last_updated']}")

        # If the last updated is more than a hour ago, delete this record
        if time.ticks_diff(time.ticks_ms(), info['last_updated']) > 60 * 60 * 1000:
            print(f"Removing sensor {sensor}")
            del sensor

        if info['temperature'] != 0 and info['name'] is not None:
            print("Sending MQTT message")
            mqtt.connect()
            message = f'{{"Time":"{now[0]}-{now[1]:02}-{now[2]:02}T{now[3]:02}:{now[4]:02}:{now[5]:02}","{info['name']}":{{"mac":"{sensor}","Temperature":{info['temperature']},"Humidity":{info['humidity']},"DewPoint":16.1,"Battery":{info['battery']},"RSSI":{info['rssi']}}},"TempUnit":"C"}}'
            mqtt.publish(topic="tele/BLESensor/SENSOR", msg=message, qos=0)
            mqtt.disconnect()

        print("-" * 20)
        print()


def handle_scan(ev, data):
    if ev == _IRQ_SCAN_RESULT:
        addr_type, addr, adv_type, rssi, adv_data = data

        if addr[0] == 0xa4:
            #print(hexlify(adv_data).decode(), len(adv_data))

            now = time.localtime()
            addr = hexlify(addr, ":").decode()

            name = battery = temperature = humidity = power = voltage = None

            if adv_data[1] == 0x09 and adv_data[0] == len(adv_data) - 1:
                name = bytes(adv_data[2:]).decode()
            
            if name is None:
                ret = parse_adv_data(adv_data)
                if ret is None:
                    print(f"Ignoring {addr}, received data not in BTHome v2 format")
                    return
                else:
                    battery, temperature, humidity, power, voltage = ret
                    print(f"{addr} - Battery:{battery}, Temperature:{temperature}, Humidity:{humidity}, Power:{power}, Voltage:{voltage} RSSI:{rssi}")
            else:
                print(f"{addr} - Device Name: '{name}'")
                pass

            # If we haven't seen this sensor before, store the results in a dictionary. Use the MAC address as a key
            if addr not in sensor_data:
                print(f"Adding New Sensor {addr}")
                sensor_data[addr] = {
                "name": name,                    # Device Name
                "temperature":  temperature,     # Celsius
                "humidity": humidity,            # Percentage
                "battery": battery,              # Percentage
                "rssi": rssi,                    # Received Signal Strength Indicator
                "voltage": voltage,              # Battery Voltage
                "power": power,                  # Power state (on/off)
                "last_updated": time.ticks_ms()  # Timestamp
            }
            else:
                # Update the values
                sensor_data[addr]["name"] = name if name is not None else sensor_data[addr]["name"]
                sensor_data[addr]["temperature"] = temperature if temperature is not None else sensor_data[addr]["temperature"]
                sensor_data[addr]["humidity"] = humidity if humidity is not None else sensor_data[addr]["humidity"]
                sensor_data[addr]["battery"] = battery if battery is not None else sensor_data[addr]["battery"]
                sensor_data[addr]["rssi"] = rssi if rssi is not None else sensor_data[addr]["rssi"]
                sensor_data[addr]["voltage"] = voltage if voltage is not None else sensor_data[addr]["voltage"]
                sensor_data[addr]["power"] = power if power is not None else sensor_data[addr]["power"]
                sensor_data[addr]["last_updated"] = time.ticks_ms()

    elif ev == _IRQ_SCAN_DONE:
        print("Scan done")
    else:
        print(f"Unexpected event: {ev}")

# BTHome data format - see https://bthome.io/format/
# 0x0e = length
# 0x16 = service data
# 0xd2 0xfc = uuid
# 0x40 = device info
# 0x00 0x20 = packet ID
# 0x01 0x64 = battery (%)
# 0x02 0xb5 0x09 = temperature (C)
# 0x03 0xfd 0x16 = humidity (%)
# 0x0c 0xef 0x0a = voltage (mV)
# 0x10 0x00 = power (on/off)

def parse_adv_data(adv_data: bytes):
    start = 0

    battery = None
    temperature = None
    humidity = None
    power = None
    voltage = None

    #print(adv_data.hex())
    len = adv_data[start]    # Length of element
    start += 1

    ServiceData = int.from_bytes(adv_data[start:start + 1], 'little', True)
    start += 1
    if ServiceData != 0x16:
        return None

    uuid = int.from_bytes(adv_data[start:start + 2], 'little', True)
    start += 2
    if uuid != 0xfcd2:  # The type we're interested in
        return None

    devinfo = int.from_bytes(adv_data[start:start + 1], 'little', True)
    start += 1
    if devinfo != 0x40:
        return None

    PacketID = int.from_bytes(adv_data[start:start + 2], 'little', True)
    start += 2

    while start < len:
        typ = int.from_bytes(adv_data[start:start+1], 'little', True)  # type of element
        start += 1
        if typ == 0x01:  # Battery
            battery = int.from_bytes(adv_data[start:start+1], 'little', True)
            start += 1
        if typ == 0x02:  # Temperature
            temperature = int.from_bytes(adv_data[start: start+2], 'little', True) / 100
            start += 2
        if typ == 0x03:  # Humidity
            humidity = int.from_bytes(adv_data[start:start+2], 'little', True) / 100
            start += 2
        if typ == 0x10:  # Power (On/Off', True)
            power = int.from_bytes(adv_data[start:start+1], 'little', True)
            start += 1
        if typ == 0x0c:  # Voltage
            voltage = int.from_bytes(adv_data[start:start+2], 'little', True) / 1000
            start += 2

    return battery, temperature, humidity, power, voltage


def DiscoverAircon():
    numtries = 5
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) #UDP
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(2)   # 2 second timeout
    sock.bind(('0.0.0.0', 49200))

    address = ('255.255.255.255', 49200)
    message = b"HF-A11ASSISTHREAD"

    while numtries > 0:
        try:
            print("Trying")
            sock.sendto(message, address)
            data, addr = sock.recvfrom(512)

            if data:
                print(f"Received: {data.decode()} from {addr}")
                sock.close()
                break
        except:
            print("No response received.")

    if data is None:
        print("No response received")
        return None

    t = tuple(data.decode().split(","))
    return t[0], t[2], t[3]


async def ReadAircon():
    print("Wait for aircon messages")
    reader, writer = await asyncio.open_connection("192.168.1.115", 9200)
    
    while True:
        data = await reader.read(1024)
        if not data:
            break
        print("Received:", data)
        
        ret = airtouch.parse_packet_header(data)
        
        if ret == None:
            print("Bad packet")
        else:
            length, msg_type, data_out = ret
            print(f"Len:{length}, Type:{msg_type}, {data_out}")
            
def StartScan():
    # Set up Bluetooth low-energy scan
    BLE().active(True)
    BLE().irq(handle_scan)
    print("Starting scan for temperature sensors...")
    #BLE().gap_scan(0, 1280000, 11250, True)  # Defaults
    BLE().gap_scan(0, 55_000, 25_250, True)  # scan often & indefinitely

# Create a timer that triggers every 60 seconds to send MQTT messages
def StartTimer():
    my_timer.init(period=60000, mode=machine.Timer.PERIODIC, callback=timer_callback)
    
def exit_handler():
    print('Application exiting')
    my_timer.deinit()
    BLE().active(False)
            
###############################################################

try:
    # Connect to the local WiFi
    connect_to_WiFi()

    webrepl.start()

    # Set the time from an NTP server
    ntptime.settime()

    # Do a discovery for an AirTouch unit on the local network
    ret = DiscoverAircon()

    if ret is not None:
        ip, name, id = ret
        print(f"Connecting to {name} on {ip}. ID={id}")
        mysock = socket.socket()
        addr = socket.getaddrinfo(ip, 9200)[0][-1]
        mysock.connect(addr)
    else:
        print("No Airtouch unit discovered. Exiting.")
        sys.exit()

    # Connect to MQTT broker
    mqtt = MQTTClient("123", "192.168.1.25", port = 1883, keepalive = 10000, ssl = False)

    # Set up Bluetooth low-energy scan
    StartScan()

    # Create a timer that triggers every 60 seconds to send MQTT messages
    StartTimer()

    # Run the web server and the receiver for aircon messages
    async def __async_main():
        task1 = asyncio.create_task(webserver.server.run())
        task2 = asyncio.create_task(ReadAircon())
        await asyncio.gather(task1, task2)

    asyncio.run(__async_main())
except Exception as e:
    print("Exception: ", e)
    exit_handler()