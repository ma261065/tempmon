from binascii import hexlify
from machine import Pin
#from bluetooth import BLE
#from webserver import server
#from webserver2 import server
from micropython import const
from time import localtime, sleep
#from struct import unpack
import machine, network, socket, ntptime, time
import asyncio
import sys
import random
from Data import UpdateData, GetData, OpenDB, CloseDB, DumpDB
from umqttsimple import MQTTClient
import aioble
import esp
import gc
#import webserver
from Logger import TemperatureLogger
from femtoweb import start_webserver

#_IRQ_SCAN_RESULT = const(5)
#_IRQ_SCAN_DONE = const(6)
TOPIC = 'tele/BLESensor/SENSOR'

#my_timer = machine.Timer(0)

# Create a ThreadSafeFlag
#tsf = asyncio.ThreadSafeFlag()

# Called once a minute
#def timer_callback(timer):
#    print("Here")
#    tsf.set()  # Signal the flag

async def scan_data_handler(result):
    #print('.', end='')
    #print(f"Device found: {result.device}  {result.device.addr} {result.name()} - {result.adv_data}, RSSI: {result.rssi}")

    if result.device.addr[0] == 0xa4:
        #print(f"Device found: {result.device}  {result.device.addr} {result.name()} - {result.adv_data}, RSSI: {result.rssi}")
        #print(hexlify(result.adv_data).decode(), len(result.adv_data))

        #now = time.localtime()
        address = hexlify(result.device.addr, ":").decode()
        name = result.name()

        battery = temperature = humidity = power = voltage = None

        #ret = None
        
        if result.adv_data is None or len(result.adv_data) == 0:
            print(f"{address} - Device Name: '{result.name()}'")
            return
        else:
            ret = parse_adv_data(result.adv_data)

        if ret is None:
            print(f"Ignoring {address}, {result.name()} = {result.adv_data} received data not in BTHome v2 format")
            return
        else:
            battery, temperature, humidity, power, voltage = ret
            print(f"{address} - Name: {name}, Battery:{battery}, Temperature:{temperature}, Humidity:{humidity}, Power:{power}, Voltage:{voltage} RSSI:{result.rssi}")

        await UpdateData(address, name, temperature, humidity, battery, result.rssi, voltage, power)
        if name is not None and temperature is not None:
            await logger.add_detailed_reading(sensor_name=address, temperature=temperature, humidity=humidity, battery_level=battery, rssi=result.rssi, voltage=voltage, power=power)

'''def handle_scan(ev, data):
    if ev == _IRQ_SCAN_RESULT:
        addr_type, addr, adv_type, rssi, adv_data = data

        if addr[0] == 0xa4:
            #print(hexlify(adv_data).decode(), len(adv_data))

            #now = time.localtime()
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

            UpdateData(addr, name, temperature, humidity, battery, rssi, voltage, power)

    elif ev == _IRQ_SCAN_DONE:
        print("Scan done")
    else:
        print(f"Unexpected event: {ev}")'''

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


async def DoNothing():
    while True:
        await asyncio.sleep_ms(100)  # This does nothing but yields control back to the event loop

async def send_mqtt():
    mqtt_connected = False

    while True:
        gc.collect()
        await asyncio.sleep(60)

        try:
            # Only connect if not already connected
            if not mqtt_connected:
                await mqtt.connect()
                mqtt_connected = True
                print("Connected to MQTT Server")
            else:
                print("Already connected to MQTT Server")

            now = time.localtime(time.time() + 3600 * 10) # Timezone is UTC+10
            print(f"Time: {now[0]}-{now[1]:02}-{now[2]:02} {now[3]:02}:{now[4]:02}:{now[5]:02}")
            print(f"Free memory: {gc.mem_free()}")

            print(logger.get_memory_info())
            print(logger.get_all_current_temps())

            SensorData = GetData()
            
            for Sensor in SensorData:
                '''ID = Sensor[0]
                Name = Sensor[1]
                Temperature = Sensor[2]
                Humidity = Sensor[3]
                Battery = Sensor[4]
                RSSI = Sensor[5]
                Voltage = Sensor[6]
                Power = Sensor[7]
                LastUpdated = Sensor[8]'''
                ID, Name, Temperature, Humidity, Battery, RSSI, Voltage, Power, LastUpdated = Sensor

                print("-" * 20)
                print(f"Sensor ID: {ID}")
                print(f"Name: {Name}")
                print(f"Temperature: {Temperature}°C")
                print(f"Humidity: {Humidity}%")
                print(f"Battery Level: {Battery}%")
                print(f"RSSI: {RSSI} dBm")
                print(f"Voltage: {Voltage}V")
                print(f"Power: {Power}")
                print(f"Last Updated: {time.ticks_ms()} - {LastUpdated} = {int(time.ticks_diff(time.ticks_ms(), LastUpdated) / 1000)} sec(s) ago")
                

                if Temperature != 0 and Temperature is not None and Name is not None:
                    print("Sending MQTT message")
                    #try:
                        #await mqtt.connect()
                        #print("Connected to MQTT Server")
                    message = f'{{"Time":"{now[0]}-{now[1]:02}-{now[2]:02}T{now[3]:02}:{now[4]:02}:{now[5]:02}","{Name}":{{"mac":"{ID}","Temperature":{Temperature},"Humidity":{Humidity},"DewPoint":16.1,"Battery":{Battery},"RSSI":{RSSI}}},"TempUnit":"C"}}'
                    await mqtt.publish(topic=TOPIC, msg=message, qos=0)
                    await asyncio.sleep_ms(10)  # Small delay between publishes
                        #await asyncio.sleep_ms(100) 
                    #except:
                        #print("Error connecting to MQTT Server")
                    #finally:
                        #print("Disconnecting")
                        #await mqtt.disconnect()
        except Exception as e:
            print(f"MQTT Error: {e}")
            mqtt_connected = False
            try:
                await mqtt.disconnect()
            except:
                pass

            await asyncio.sleep(5)  # Wait before retry

        print("-" * 20)
        print()

async def scan_ble():
    while True:
        gc.collect()
        #print('*', end='')
        async with aioble.scan(
            #duration_ms=50,        # Total duration of the scan in milliseconds was 100
            #interval_us=30000,     # Scan interval in microseconds was 55_000
            #window_us=30000,       # Scan window in microseconds was 25_250
            duration_ms=5000,       # Total duration of the scan in milliseconds
            interval_us=50000,     # Scan interval in microseconds
            window_us=25000,       # Scan window in microseconds
            active=True            # Active scan mode
        ) as scanner:
            async for result in scanner:
                #print('<', end='') #result.device.addr)
                await scan_data_handler(result)
                #print('>', end='')

'''def StartBTScan():
    # Set up Bluetooth low-energy scan
    BLE().active(True)
    BLE().irq(handle_scan)
    print("Starting scan for temperature sensors...")
    #BLE().gap_scan(0, 1280000, 11250, True)  # Defaults
    BLE().gap_scan(0, 55_000, 25_250, True)  # scan often & indefinitely'''

# Create a timer that triggers every 60 seconds to send MQTT messages
#def StartTimer():
#    my_timer.init(period=60000, mode=machine.Timer.PERIODIC, callback=timer_callback)
    
def exit_handler():
    print('Application exiting')
    if mqtt is not None:
        mqtt.disconnect()
    #my_timer.deinit()
    #BLE().active(False)
    #CloseDB()
    sys.exit()

    
###############################################################

#try:
# Connect to WiFi happens in boot.py

esp.osdebug(0)

# Use external Antenna on C6
WIFI_SWITCH_ENABLE = Pin(3, Pin.OUT)
WIFI_ANT_CONFIG = Pin(14, Pin.OUT)
WIFI_SWITCH_ENABLE.value(0)
WIFI_ANT_CONFIG.value(1)

# Set the time from an NTP server
ntpretries = 5
for attempt in range(ntpretries):
    try:
        print(f"Setting time from NTP server... (attempt {attempt + 1}/{ntpretries})")
        ntptime.settime()
        print("Time set successfully")
        break
    except Exception as e:
        print(f"Failed to set time: {e}")
        if attempt < ntpretries - 1:  # Don't sleep after the last attempt
            sleep(2)
else:
    print("Failed to set time")
    exit_handler()

# Connect to MQTT broker
try:
    MQTTHost = socket.getaddrinfo('raspberrypi.local', 1883)[0][4][0]
    print("MQTT host found at", MQTTHost)
except:
    print("MQTT Host not found")
    exit_handler()

mqtt = MQTTClient("123", MQTTHost, port = 1883, keepalive = 10000, ssl = False)
#client = MQTTClient(config)

logger = TemperatureLogger(2880)  # 24 hours at one reading every 5 minutes x 10 sensors
#OpenDB()

# Set up Bluetooth low-energy scan
#StartBTScan()

# Create a timer that triggers every 60 seconds to send MQTT messages
#StartTimer()

# Run the BLE scan, MQQT publish, web server and any other async tasks
try:
    loop = asyncio.get_event_loop()
    loop.create_task(start_webserver(logger))
    #loop.create_task(server.run())
    loop.create_task(scan_ble())
    loop.create_task(send_mqtt())
    loop.run_forever()

except Exception as e:
    print("Exception in main loop:", e)
    exit_handler()

'''async def __async_main():
#asyncio.create_task(scan_ble())
#asyncio.create_task(send_mqtt())
asyncio.create_task(server())

# Keep the main coroutine alive (infinite loop)
while True:
    await asyncio.sleep_ms(1000)

asyncio.run(__async_main())'''