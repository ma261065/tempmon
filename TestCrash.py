import aioble
import asyncio
import gc

async def scan_ble():
    while True:
        async with aioble.scan(
            duration_ms=50,        # Total duration of the scan in milliseconds
            interval_us=30000,     # Scan interval in microseconds
            window_us=30000,       # Scan window in microseconds
            active=True            # Active scan mode
        ) as scanner:
            async for result in scanner:
                await scan_data_handler(result)

async def scan_data_handler(result):
    print(f"Device found: {result.device}  {result.device.addr} {result.name()} - {result.adv_data}, RSSI: {result.rssi}")


gc.collect()
print(gc.mem_free())
buf = bytearray(40000)
gc.collect()
print(gc.mem_free())

loop = asyncio.get_event_loop()
loop.create_task(scan_ble())
loop.run_forever()