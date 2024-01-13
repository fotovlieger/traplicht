from math import *
import time
from utime import ticks_diff, ticks_ms
import asyncio
import json				# for cfg
import sys				# for exit

from bh1750 import BH1750
from machine import Pin, I2C, SoftI2C
from neopixel import NeoPixel

from microdot_asyncio import Microdot, Response, send_file
from microdot_utemplate import render_template
from microdot_asyncio_websocket import with_websocket

# ------- load cfg -------
cfg = {
    'luxOn':    40,   # leds on if darker than this
    'luxOff':   30,   # must be <luxOn, hystheresis
    'timeOff':  10,	  # switch off time
    'mode':     'auto',  #auto, on, off
}

state = {
    'light'  :     0,
    'mov1':     0,
    'mov2':     0,
    'mov':      0,
    'movT':     0,	#timestamp last mov (ms)
    'movD':     0,	#count down in %
    'on':       False,
}

# Save cfg to a file
def saveCfg():
    with open("/cfg.json", "w") as file:
        json.dump(cfg, file)

# Load cfg from a file
def loadCfg():
    try:
        with open("/cfg.json", "r") as file:
            cfg.update(json.load(file))
        print("cfg loaded.")
    except OSError:
        pass

loadCfg()
saveCfg()

print(json.dumps(cfg))

# Initialize MicroDot
app = Microdot()
Response.default_content_type = 'text/html'

LEDS    = 111
LUX_MAX = 500
LUX_MIN = 20

lux = 0.0
pir = 0

#pin 34/35 werkt nie !?!?!

i2c = SoftI2C(scl=Pin(27),sda=Pin(14),freq=100000)
i2c.scan()

light   = BH1750(i2c)
strip1  = NeoPixel(Pin(26), LEDS, 3, 1)  #400kHz 0->800kHz
strip2  = NeoPixel(Pin(25), LEDS, 3, 1)  #400kHz 0->800kHz
strip3  = NeoPixel(Pin(33), LEDS, 3, 1)  #400kHz 0->800kHz
strip4  = NeoPixel(Pin(32), LEDS, 3, 1)  #400kHz 0->800kHz

# 36=SP, 39=SN
mov1  = Pin(39, Pin.IN)
mov2  = Pin(36, Pin.IN)

async def calc():
    cnt = 0
    while True:
        if   cfg['mode'] == 'on':
            state['on'] = True
        elif cfg['mode'] == 'auto':
            # hystherese
            if state['on']:
                limit = cfg['luxOn']
            else:
                limit = cfg['luxOff']
            state['on'] = state['light']<limit and state['movD']>0
        else:
            state['on'] = False
        
        if cnt % 5 == 0:
          print(json.dumps(state))
        cnt = cnt+1
        await asyncio.sleep(0.1)  # Sleep before next iteration
        
async def update_strip():
    while True:
        if state['on']:
            strip1.fill(( 0, 0, 0))
            strip2.fill((80,30, 0))
            strip3.fill((80,30, 0))
            strip4.fill((80,30, 0))
            
            for i in range(int(LEDS * state['movD'])): 
                strip1[i]=(255,70,0)
                
            # debug
            for i in range(5):
                strip1[i]=(0,0,0)
                strip2[i]=(0,0,0)
                strip3[i]=(0,0,0)
            strip2[0]=(250, 0, 0)
            strip3[0]=( 0,250, 0)
            strip4[0]=( 0, 0,250)

        else:
            strip1.fill(( 0, 0, 0))
            strip2.fill(( 0, 0, 0))
            strip3.fill(( 0, 0, 0))
            strip4.fill(( 0, 0, 0))
            
        strip1.write()
        strip2.write()
        strip3.write()
        strip4.write()
        await asyncio.sleep(0.2)  # Sleep for 1 second before next iteration
        

async def read_light():
    while True:
        lux = light.luminance(BH1750.ONCE_HIRES_1)
        state['light'] = round(lux, 1)
        await asyncio.sleep(0.5)  # Sleep before next iteration
        
# read mov sensors
async def read_mov():
    while True:
        # Perform your asynchronous operations here
        state['mov1'] = mov1.value()
        state['mov2'] = mov2.value()
        state['mov']  = state['mov1'] or state['mov2']
        # movD: decays form 1 to 0
        if state['mov']:
            state['movT'] = ticks_ms()
            state['movD'] = 1
        else:
            dt = ticks_diff(ticks_ms(), state['movT']) / 1000
            state['movD'] = round(max(0, 1-dt/cfg['timeOff']),2)
            
        await asyncio.sleep(0.1)  # Sleep before next iteration


loop = asyncio.get_event_loop()
loop.create_task(update_strip())
loop.create_task(read_light())
loop.create_task(read_mov())
loop.create_task(calc())

# root route
@app.route('/')
async def index(request):
    print('index')
    return render_template('index.html')

@app.route('/ws')
@with_websocket
async def read_sensor(request, ws):
    t0=0
    while True:
        #data = await ws.receive()
        time.sleep(0.4)
        await ws.send(str(state['light']))

# Static CSS/JSS
@app.route("/static/<path:path>")
def static(request, path):
    if ".." in path:
        # directory traversal is not allowed
        return "Not found", 404
    return send_file("static/" + path)


# shutdown
@app.get('/shutdown')
def shutdown(request):
    request.app.shutdown()
    return 'The server is shutting down...'


if __name__ == "__main__":
    try:
        app.run()
    except KeyboardInterrupt:
        pass