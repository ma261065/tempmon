import webrepl
import esp32
import network
from machine import Pin

def connect_to_WiFi():
# If we're running on a Seeed C6 switch to the external antenna
    #WIFI_SWITCH_ENABLE = Pin(3, Pin.OUT)
    #WIFI_ANT_CONFIG = Pin(14, Pin.OUT)

    #WIFI_SWITCH_ENABLE.value(0)
    #WIFI_ANT_CONFIG.value(1)

    # Get the access point and password from non-volatile storage
    nvs = esp32.NVS("keys")
    buf = bytearray(32)
    nvs.get_blob("ap", buf)
    ap = buf.rstrip(b'\x00').decode('utf-8')
    nvs.get_blob("pw", buf)
    pw = buf.rstrip(b'\x00').decode('utf-8')
    
    network.hostname("tempmon")
    sta_if = network.WLAN(network.STA_IF)

    if not sta_if.isconnected():
        sta_if.active(True)
        print(f"Connecting to WiFi {ap}...")
        #mac = sta_if.config('mac')
        #host = 'esp32-' + ''.join('{:02x}'.format(b) for b in mac[3:])
        #host = 'tempmon'
        #sta_if.config(dhcp_hostname = host)
        sta_if.connect(ap, pw)

        while not sta_if.isconnected():
            pass

    #host = sta_if.config('dhcp_hostname')
    print('Wifi connected as {}/{}, net={}, gw={}, dns={}'.format(network.hostname(), *sta_if.ifconfig()))
    
# Connect to the local WiFi
connect_to_WiFi()

# Start the webrepl server on port 8266
webrepl.stop()
webrepl.start()