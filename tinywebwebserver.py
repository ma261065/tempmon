#from nanoweb import HttpError, Nanoweb, send_file
from server import webserver
import asyncio
from Data import Get_Temp
import time
import json
import sys

# Create web server application
server = webserver()

# Run the tinyweb server in an asyncio compatible way
async def run_server():
    # This function will start the tinyweb server (which is blocking)
    # We use asyncio's run_in_executor to prevent it from blocking the event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, server.run, '0.0.0.0', 80)

ASSETS_DIR = './assets/'

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
async def api_status(request, response):
    """API status endpoint"""
    await response.send("HTTP/1.1 200 OK\r\n")
    await response.send("Content-Type: application/json\r\n\r\n")

    time_str, uptime_str = get_time()

    await response.send(json.dumps({
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

@server.route('/tempdata')
async def tempdata(request, response):
    UTC_OFFSET = 10 * 60 * 60
    current_time = time.localtime(time.time() + UTC_OFFSET)
    formatted_time = "{:02d}:{:02d}".format(current_time[3], current_time[4])
    ty = f'{{"time": "{formatted_time}", "temperature": "{Get_Temp()}"}}'
    await response.send(b"HTTP/1.1 200 Ok\r\n\r\n")
    await response.send(ty)

@server.route('/')
async def index(request, response):
    #await response.start_html()
    #await response.send(b"HTTP/1.1 200 Ok\r\n\r\n")
    #await response.send('<html><body><h1>Hello, world! (<a href="/table">table</a>)</h1></html>\n')
    await response.send_file('%sindex.html' % ASSETS_DIR)

@server.route('/default.js')
async def index(request, response):
    #await response.start_html()
    #await response.send(b"HTTP/1.1 200 Ok\r\n\r\n")

    await response.send_file('%sdefault.js' % ASSETS_DIR)

@server.route('/assets/<fn>')
async def assets(request, response, fn):
    print("Got:", fn)
    await response.send("HTTP/1.1 200 OK\r\n")

    args = {}

    filename = fn #request.url.split('/')[-1]

    '''if filename.endswith('.png'):
        args = {'binary': True}

    if filename.endswith('.svg'):
        await request.write("Content-Type: image/svg+xml\r\n\r\n")
        args = {'binary':False}

    await response.send("\r\n")
    await response.send_file(
        './%s/%s' % (ASSETS_DIR, filename),
        **args,
     )'''
    await response.send_file('%s%s' % (ASSETS_DIR, filename), content_type='image/png')

    
@server.route('/shutdown')
async def shutdown(request, response):
    args = {}
    await response.send("HTTP/1.1 200 OK\r\n\r\n")
    await response.send_file(
        '%s' % ('html.py'),
        **args,
    )