import asyncio
import aioble
import sys
import uerrno
import time
import json

#from testmq import MQTTClient
#from umqttsimple import MQTTClient

def get_time():
    uptime_s = int(time.ticks_ms() / 1000)
    uptime_h = int(uptime_s / 3600)
    uptime_m = int(uptime_s / 60)
    uptime_m = uptime_m % 60
    uptime_s = uptime_s % 60
    return (
        '{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(*time.localtime()),
        '{:02d}h {:02d}:{:02d}'.format(uptime_h, uptime_m, uptime_s),
    )

async def serve(writer, filename):
    if filename == '/':
        filename = 'index.html'

    print("Sending", filename)
    
    if filename.startswith("/api/status"):
        await writer.awrite(b"HTTP/1.1 200 OK\r\n")
        await writer.awrite("Content-Type: application/json\r\n\r\n")

        time_str, uptime_str = get_time()

        await writer.awrite(json.dumps({
            "time": time_str,
            "uptime": uptime_str,
            'python': '{} {}'.format(
                sys.implementation.name,
                '.'.join(
                    str(s) for s in sys.implementation.version
                ),
            ),
            'platform': str(sys.platform),
        }))
        
        await writer.drain()

        print("Closing connection", writer)
        await writer.aclose()
        await writer.wait_closed()
        return

    if filename.startswith("/tempdata"):
        await writer.awrite(b"HTTP/1.1 200 OK\r\n")
        await writer.awrite("Content-Type: application/json\r\n\r\n")

        UTC_OFFSET = 10 * 60 * 60
        current_time = time.localtime(time.time() + UTC_OFFSET)
        formatted_time = "{:02d}:{:02d}".format(current_time[3], current_time[4])
        ty = f'{{"time": "{formatted_time}", "temperature": "{26.26}"}}'
        
        await writer.awrite(ty)
        await writer.drain()

        print("Closing connection", writer)
        await writer.aclose()
        await writer.wait_closed()
        return

    await writer.awrite(b"HTTP/1.1 200 OK\r\n\r\n")
    try:
        with open(f"./assets/{filename}", 'rb') as f:
            while True:
                data = f.read(64)
                if not data:
                    break
                await writer.awrite(data)
                await writer.drain()
    except OSError as e:
        if e.args[0] != uerrno.ENOENT:
            print("Error:", e.args[0])
        else:
            print("File Not Found")

    print("Sent")
    print("Closing connection", writer)
    await writer.aclose()
    await writer.wait_closed()

async def handle(reader, writer):
    print("***********************************************", reader)
    try:
        while True:
            items = await asyncio.wait_for(reader.readline(), timeout=5)

            if len(items) == 0:
                break

            items = items.decode('ascii').split()

            if len(items) > 0 and items[0] == 'GET':
                filename = items[1]

            #print(len(items), items)

            if len(items) == 0:
                await serve(writer, filename)
                break
            
    except asyncio.TimeoutError:
        print("Timeout occurred. Closing connection", reader)
        await writer.aclose()
        await writer.wait_closed()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Finished")
        
async def start_webserver():
    await asyncio.start_server(handle, '0.0.0.0', 80)

async def scan_blea():
    while True:
        async with aioble.scan(
            duration_ms=50,        # Total duration of the scan in milliseconds was 100
            interval_us=30000,     # Scan interval in microseconds was 55_000
            window_us=30000,       # Scan window in microseconds was 25_250
            active=True            # Active scan mode
        ) as scanner:
            async for result in scanner:
                print('@', end='') #result.device.addr)


try:
    loop = asyncio.get_event_loop()
    loop.create_task(start_webserver())
    loop.create_task(scan_blea())
    loop.run_forever()

except Exception as e:
    print("Exception:", e)