import time
#import btree

# Create an empty dictionary to store sensor data
sensor_data = {}
db = None
f = None

def OpenDB():
    pass
    '''global f
    global db

    try:
        f = open("temps.db", "r+b")
    except OSError:
        f = open("temps.db", "w+b")

    db = btree.open(f)'''

def CloseDB():
    global f
    global db

    if db is not None:
        db.close()

    if f is not None:
        f.close()

def DumpDB():
    global f
    global db

    Target = "da:5e:ca"
    hex_addr = Target.split(':')
    last_three_hex = hex_addr[-3:]
    addr_bytes = bytes(int(value, 16) for value in last_three_hex)

    # Print the "Parents" temp values
    for key in db.keys(addr_bytes + bytes.fromhex("0000"), addr_bytes + bytes.fromhex("059f")):
        last_two_bytes = key[-2:]
        minutes_since_midnight = int.from_bytes(last_two_bytes, 'big')

        print(f"{minutes_since_midnight // 60:02d}:{minutes_since_midnight % 60:02d}", end='-')
        print(int.from_bytes(db[key], 'big') / 100, end=', ')

def GetData():
    l = list()
    now = time.ticks_ms()

    for sensor, info in sensor_data.items():
        # If the last updated is more than a hour ago, delete this record
        if time.ticks_diff(now, info['last_updated']) > 60 * 60 * 1000:
            print(f"Removing sensor {sensor} - {now} {info['last_updated']}")
            del sensor_data[sensor]
            continue

        # Build a list of tuples with the sensor data
        t = tuple((sensor, info['name'], info['temperature'], info['humidity'], info['battery'], info['rssi'], info['voltage'], info['power'], info['last_updated']))
        l.append(t)

    return(l)

async def UpdateData(addr, name, temperature, humidity, battery, rssi, voltage, power):
    global f
    global db
    
    if temperature is not None:
        # Store this value in the database. The key is the last three bytes of the address & the time in secs since midnight
        '''t = time.localtime(time.time() + 3600*10)
        minutes_since_midnight = t[3]*60 + t[4]
        time_bytes = minutes_since_midnight.to_bytes(2, 'big')

        hex_addr = addr.split(':')
        last_three_hex = hex_addr[-3:]
        addr_bytes = bytes(int(value, 16) for value in last_three_hex)
        key = addr_bytes + time_bytes

        value = int(temperature * 100).to_bytes(2, 'big')
        db[key] = value
        #Unhandled exception in IRQ callback handler
        #Traceback (most recent call last):
        # File "<stdin>", line 119, in handle_scan
        # File "Data.py", line 79, in UpdateData
        # OSError: 0
        db.flush()'''

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
        #print("Updated to ", sensor_data[addr]["last_updated"])


def Get_Temp():
    return(sensor_data['a4:c1:38:da:5e:ca']["temperature"])