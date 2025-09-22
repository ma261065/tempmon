# Drop-in replacement for MicroPython web server with memory optimizations
import asyncio
import aioble
import sys
import uerrno
import time
import json

UTC_OFFSET = 10 * 60 * 60

# OPTIMIZED: Pre-allocated buffers to avoid frequent allocations
_file_buffer = bytearray(512)  # For file reading (larger chunks than original 64 bytes)
_temp_dict = {}  # Reusable dictionary for JSON responses
_history_list = []  # Reusable list for history data

def get_time():
    uptime_s = int(time.ticks_ms() / 1000)
    uptime_h = int(uptime_s / 3600)
    uptime_m = int(uptime_s / 60)
    uptime_m = uptime_m % 60
    uptime_s = uptime_s % 60
    return (
        '{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(*time.localtime(time.time() + UTC_OFFSET)),
        '{:02d}h {:02d}m {:02d}s'.format(uptime_h, uptime_m, uptime_s),
    )

routes = {}

#Route decorator - keeping original commented code
'''def route(route):
    def decorator(func):
        routes[route] = func
        return func
    return decorator'''

#route('/settings.html') - keeping original commented code
async def index(mywriter):
    filename = "settings.html"
    print("xx")
    await mywriter.awrite(b"HTTP/1.1 200 OK\r\n")
    await mywriter.drain()
    print("Sending - ", filename)
    
    try:
        with open(f"./assets/{filename}", 'rb') as f:
            while True:
                # OPTIMIZED: Use larger buffer reads instead of 64 bytes
                bytes_read = f.readinto(_file_buffer)
                if bytes_read == 0:
                    break
                print('.', end='')
                # Original code was commented out, keeping it commented
                #await mywriter.awrite(data)
                #await mywriter.drain()
    except OSError as e:
        print("Error")

    #    if e.args[0] != uerrno.ENOENT:
    #        print("Error:", e.args[0])
    #    else:
    #        print("File Not Found")
    #await send_file(mywriter, "settings.html")
    print("Closing connection", writer)
    await writer.aclose()
    await writer.wait_closed()

async def doodle(writer, filename):
    await writer.awrite(b"HTTP/1.1 200 OK\r\n\r\n")
    try:
        with open(f"./assets/{filename}", 'rb') as f:
            while True:
                # OPTIMIZED: Use pre-allocated buffer instead of f.read(64)
                bytes_read = f.readinto(_file_buffer)
                if bytes_read == 0:
                    break
                
                # Send only the bytes we actually read
                if bytes_read == len(_file_buffer):
                    await writer.awrite(_file_buffer)
                else:
                    await writer.awrite(_file_buffer[:bytes_read])
                await writer.drain()
    except OSError as e:
        if e.args[0] != uerrno.ENOENT:
            print("Error:", e.args[0])
        else:
            print("File Not Found")

# Keeping original commented send_file function
'''async def send_file(ttwriter, filename):
    print("Sending - ", filename)
    try:
        with open(f"./assets/{filename}", 'rb') as f:
            while True:
                data = f.read(64)
                print('.', end='')
                if not data:
                    break
                await ttwriter.awrite(data)
                await ttwriter.drain()
    except OSError as e:
        if e.args[0] != uerrno.ENOENT:
            print("Error:", e.args[0])
        else:
            print("File Not Found")'''

async def serve(writer, filename, logger):
    print("Sending", filename)
    
    if filename == '/':
        filename = 'index.html'
    
    #if filename.startswith("/settings.html"):
    #    await index(writer)
        #if filename in routes:
        #print("Routing to ", routes[filename])
        #await index(writer)
        #await routes[filename](writer)'''
    # return
    
    if filename.startswith("/api/status"):
        await writer.awrite(b"HTTP/1.1 200 OK\r\n")
        await writer.awrite("Content-Type: application/json\r\n\r\n")

        time_str, uptime_str = get_time()

        # OPTIMIZED: Reuse dictionary instead of creating new one
        _temp_dict.clear()
        _temp_dict["time"] = time_str
        _temp_dict["uptime"] = uptime_str

        await writer.awrite(json.dumps(_temp_dict))
        
        await writer.drain()

        print("Closing connection", writer)
        await writer.aclose()
        await writer.wait_closed()
        return
    
    if filename.startswith("/api/history"):
        await writer.awrite(b"HTTP/1.1 200 OK\r\n")
        await writer.awrite("Content-Type: application/json\r\n\r\n")

        # OPTIMIZED: Use efficient sensor history retrieval
        temp_data = logger.get_sensor_history("a4:c1:38:da:5e:ca", max_readings=24*12)

        if not temp_data:
            await writer.awrite("{}")
            await writer.drain()
            await writer.aclose()
            await writer.wait_closed()
            return
    
        # OPTIMIZED: Reuse history list instead of creating new one
        _history_list.clear()
        for timestamp_since_epoch, temperature in temp_data:
            time_tuple = time.localtime(timestamp_since_epoch + UTC_OFFSET)
            hh_mm = f"{time_tuple[3]:02d}:{time_tuple[4]:02d}"
            
            _history_list.append({
                "time": hh_mm,
                "temperature": f"{temperature:.2f}",
            })
        
        await writer.awrite(json.dumps(_history_list))
        await writer.drain()

        print("Closing connection", writer)
        await writer.aclose()
        await writer.wait_closed()
        return

    if filename.startswith("/tempdata"):
        await writer.awrite(b"HTTP/1.1 200 OK\r\n")
        await writer.awrite("Content-Type: application/json\r\n\r\n")

        current_time = time.localtime(time.time() + UTC_OFFSET)
        formatted_time = "{:02d}:{:02d}".format(current_time[3], current_time[4])
        
        # OPTIMIZED: Use more efficient current temperature retrieval
        current_temps = logger.get_all_current_temps(max_age_minutes=10)
        temp = current_temps.get("a4:c1:38:da:5e:ca")

        # Get total data point count for this sensor
        total_count = logger.get_sensor_data_count("a4:c1:38:da:5e:ca")

        ty = f'{{"time": "{formatted_time}", "temperature": "{temp}", "totalDataPoints": {total_count}}}'
           
        await writer.awrite(ty)
        await writer.drain()

        print("Closing connection", writer)
        await writer.aclose()
        await writer.wait_closed()
        return

    #await doodle(writer, filename)
    
    try:
        with open(f"./assets/{filename}", 'rb') as f:
            await writer.awrite(b"HTTP/1.1 200 OK\r\n")
            
            if filename.endswith('.svg'):
                await writer.awrite(b"Content-Type: image/svg+xml\r\n")

            await writer.awrite(b"\r\n")

            while True:
                # OPTIMIZED: Use pre-allocated buffer for larger, more efficient reads
                bytes_read = f.readinto(_file_buffer)

                if bytes_read == 0:
                    break

                # Send only the bytes we actually read
                if bytes_read == len(_file_buffer):
                    await writer.awrite(_file_buffer)
                else:
                    await writer.awrite(_file_buffer[:bytes_read])
                await writer.drain()
    except OSError as e:
        if e.args[0] != uerrno.ENOENT:
            print("Error:", e.args[0])
        else:
            print(filename, "not found")
        await writer.aclose()
        await writer.wait_closed()
        return

    print("Sent", filename)
    print("Closing connection", writer)
    await writer.aclose()
    await writer.wait_closed()

async def handle(reader, writer, logger):
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
                await serve(writer, filename, logger)
                break
            
    except asyncio.TimeoutError:
        print("Timeout occurred. Closing connection", reader)
        await writer.aclose()
        await writer.wait_closed()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Finished")
        
# Keeping original commented function
#async def start_webserver(logger):
#    await asyncio.start_server(handle, '0.0.0.0', 80)

async def start_webserver(logger):
    # Create the server and pass logger to handle
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, logger), '0.0.0.0', 80
    )
    # No need for serve_forever; let the event loop manage the server
    return server  # Keep the server alive by returning it

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

# Keeping original commented main loop
'''try:
    loop = asyncio.get_event_loop()
    loop.create_task(start_webserver())
    loop.create_task(scan_blea())
    loop.run_forever()

except Exception as e:
    print("Exception:", e)'''

# OPTIMIZED: Additional helper functions for memory management (optional to use)

def print_memory_stats():
    """Optional: Print memory statistics if available"""
    try:
        import gc
        gc.collect()  # Force garbage collection
        free = gc.mem_free()
        allocated = gc.mem_alloc()
        print(f"Memory: {allocated} used, {free} free, {allocated+free} total")
    except:
        print("Memory stats not available")

async def periodic_gc():
    """Optional: Periodic garbage collection task"""
    while True:
        await asyncio.sleep(30)  # Every 30 seconds
        try:
            import gc
            gc.collect()
        except:
            pass

# Optional usage example with memory monitoring
'''
async def main_with_gc(logger):
    """Optional: Enhanced main with garbage collection"""
    server = await start_webserver(logger)
    
    # Start periodic garbage collection
    asyncio.create_task(periodic_gc())
    
    # Start scanning
    await scan_blea()
'''