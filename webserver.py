from nanoweb import HttpError, Nanoweb, send_file
from Data import Get_Temp
import time
import json
import sys

ASSETS_DIR = './assets'

server = Nanoweb(80)
server.assets_extensions += ('ico',)
server.STATIC_DIR = ASSETS_DIR

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
    
@server.route('/api/status')
async def api_status(request):
    """API status endpoint"""
    await request.write.awrite("HTTP/1.1 200 OK\r\n")
    await request.write.awrite("Content-Type: application/json\r\n\r\n")
    

    time_str, uptime_str = get_time()

    await request.write.awrite(json.dumps({
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
    await request.write.drain()

    
@server.route('/')
async def index(request):
    await request.write.awrite(b"HTTP/1.1 200 Ok\r\n\r\n")
    await request.write.drain()
    await send_file(
        request,
        '%s/index.html' % ASSETS_DIR
    )

@server.route('/tempdata')
async def index(request):
    UTC_OFFSET = 10 * 60 * 60
    current_time = time.localtime(time.time() + UTC_OFFSET)
    formatted_time = "{:02d}:{:02d}".format(current_time[3], current_time[4])
    ty = f'{{"time": "{formatted_time}", "temperature": "{Get_Temp()}"}}'
    await request.write.awrite(b"HTTP/1.1 200 Ok\r\n\r\n")
    await request.write.awrite(ty)
    await request.write.drain()

@server.route('/assets/*')
async def assets(request):
    await request.write.awrite("HTTP/1.1 200 OK\r\n")
    await request.write.drain()

    args = {}

    filename = request.url.split('/')[-1]
    print("File:", filename)

    if filename.endswith('.png'):
        args = {'binary': True}

    if filename.endswith('.svg'):
        await request.write.awrite("Content-Type: image/svg+xml\r\n\r\n")
        await request.write.drain()
        args = {'binary':False}

    await request.write.awrite("\r\n")
    await request.write.drain()
    print("here")
    await send_file(
        request,
        '%s/%s' % (ASSETS_DIR, filename),
        **args,
    )
    
@server.route('/shutdown')
async def shutdown(request):
    args = {}
    await request.write.awrite("HTTP/1.1 200 OK\r\n\r\n")
    await request.write.drain()
    await send_file(
        request,
        '%s' % ('html.py'),
        **args,
    )
    
#@server.route('/', methods=['POST'])
#async def Button(request):
#    AirTouch.TurnAirconOn(sock)
#    return 'OK'    