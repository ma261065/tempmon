from microdot import Microdot, send_file
from Data import Get_Temp
import time
import json
import sys

app = Microdot()

async def server():
    await app.start_server(port=80, debug=True)

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

@app.route('/')
async def index(request):
    return send_file('assets/index.html')

@app.route('/settings.html')
async def settings(request):
    return 'Hello, world!'
    #return send_file('/assets/settings.html')

@app.route('/favicon.ico')
async def icon(request):
    return send_file('assets/favicon.ico')

@app.route('/thermo.png')
async def thermo(request):
    return send_file('assets/thermo.png')

@app.route('/default.js')
async def js(request):
    return send_file('assets/default.js')   

@app.route('/default.css')
async def css(request):
    return send_file('assets/default.css')   

'''@app.route('/tempdata')
async def tempdata(request):
    UTC_OFFSET = 10 * 60 * 60
    current_time = time.localtime(time.time() + UTC_OFFSET)
    formatted_time = "{:02d}:{:02d}".format(current_time[3], current_time[4])
    ty = f'{{"time": "{formatted_time}", "temperature": "{Get_Temp()}"}}'
    return ty'''

@app.route('/api/status')
async def api_status(request):
    time_str, uptime_str = get_time()

    return json.dumps({
        "time": time_str,
        "uptime": uptime_str,
        'python': '{} {}'.format(
            sys.implementation.name,
            '.'.join(
                str(s) for s in sys.implementation.version
            ),
        ),
        'platform': str(sys.platform),
    })