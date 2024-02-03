###########################################################
# Trap
###########################################################
from math import *
import time
from utime import ticks_diff, ticks_ms
import asyncio
import json				# for cfg

from bh1750 import BH1750
from machine import Pin, I2C, SoftI2C
from neopixel import NeoPixel

from microdot_asyncio import Microdot, Response, send_file
from microdot_asyncio_websocket import with_websocket

# ------- load cfg -------
cfg = {
    'luxOn':    40,   # leds on if darker than this
    'luxOff':   30,   # must be <luxOn, hystheresis
    'timeOff': 120,	  # switch off time
    'mode':     'auto',  #auto, on, off
    'color':    '80,30, 0',
}

state = {
    'light'  :  0,
    'mov':      0,
    'movT':     0,	#timestamp last mov (ms)
    'movD':     0,	#count down in %
    'on':       False,
}

webState = {			# state shared among connected web pages
    'mode' : 'auto',
    'color': '20,0,0',
}

# list of connected websockets: added when a client connects,
# removed when sending an update fails.
connections = {
}

# Save cfg to a file
def saveCfg():
    with open("/cfg.json", "w") as file:
        json.dump(cfg, file)
        print('saveCfg', cfg)
        
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

webState['color'] = cfg['color']
webState['mode']  = cfg['mode']

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
#i2c.scan()
try:
    light   = BH1750(i2c)
except:
    light	= False
    

strip1  = NeoPixel(Pin(26), LEDS, 3, 1)  #1->400kHz 0->800kHz
strip2  = NeoPixel(Pin(25), LEDS, 3, 1)  #400kHz 0->800kHz
strip3  = NeoPixel(Pin(33), LEDS, 3, 1)  #400kHz 0->800kHz
strip4  = NeoPixel(Pin(32), LEDS, 3, 1)  #400kHz 0->800kHz

mov  = Pin(39, Pin.IN)   # 39=SN

async def calc():
    while True:
        if   webState['mode'] == 'on':
            state['on'] = True
        elif webState['mode'] == 'auto':
            # hystherese
            if state['on']:
                limit = cfg['luxOn']
            else:
                limit = cfg['luxOff']
            state['on'] = state['light']<limit and state['movD']>0
        else:
            state['on'] = False

        await asyncio.sleep(.2)  # Sleep before next iteration
        
async def update_strip():
    while True:
        rgb = list(map(int, webState['color'].split(',')))
        if len(rgb) == 3:
            # dim if too bright (max LED current)
            bright = rgb[0]+rgb[1]+rgb[2]
            if bright > 300:
                fac = 300/bright
                rgb = [int(fac * x) for x in rgb]
        else:
            rgb = (30,0,0)
            

        if state['on']:
            strip1.fill(rgb)
            if webState['mode']=='auto':
                rgbLow = [int(0.8*state['movD']*x) for x in rgb]
            else:
                rgbLow = [int(0.5*x) for x in rgb]

            strip2.fill(rgbLow)
            strip3.fill(rgbLow)
            strip4.fill(rgbLow)

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
        if light:
            lux = light.luminance(BH1750.ONCE_HIRES_1)
        else:
            lux=100
        state['light'] = round(lux, 1)
        await asyncio.sleep(1)  # Sleep before next iteration
        
# read mov sensors
async def read_mov():
    while True:
        state['mov']  = mov.value()
        # movD: decays form 1 to 0
        if state['mov']:
            state['movT'] = ticks_ms()
            state['movD'] = 1
        else:
            dt = ticks_diff(ticks_ms(), state['movT']) / 1000
            state['movD'] = round(max(0, 1-dt/cfg['timeOff']),2)
            
        await asyncio.sleep(0.1)  # Sleep before next iteration

# send update to selected client
async def sendUpdate(addr, msg):
    ws = connections[addr]
    try:
        await ws.send(msg)
        print('sendUpdate', addr, msg)
    except:
        print('close', addr)
        connections.pop(addr)

# Web update task: send webState to all connected pages
# when data has changed
async def updateWebClients():
    t0 = 0
    oldVal = ''
    while True:
        t = time.ticks_ms()       
        if ticks_diff(t, t0) > 1e3:  #ms!
            # update values once in a while 
            webState['light'] = state['light']
            webState['mov'] = state['mov']
            webState['movD'] = state['movD']
            webState['on'] = state['on']
            t0 = t
            print(json.dumps(state))
            
        newVal = json.dumps(webState)
        if oldVal != newVal:
            oldVal = newVal
            for addr in connections:
                await sendUpdate(addr, newVal)
                
        await asyncio.sleep(.2)  # Sleep before next check
        

def updateMode(data, id):
    webState[id] = data[id]
    
def updateColor(data, id):
    webState[id] = data[id]

def saveConfig(data, id):
    if data[id] == 'true':
        cfg['mode']  = webState['mode']
        cfg['color'] = webState['color']
        saveCfg()        
    
def onUpdate(data):
    if 'mode' in data:
        updateMode(data, 'mode')
    if 'color' in data:
        updateColor(data, 'color')
    if 'saveConfig' in data:
        saveConfig(data, 'saveConfig')
    print('onUpdate', webState)
    
loop = asyncio.get_event_loop()
loop.create_task(update_strip())
loop.create_task(read_light())
loop.create_task(read_mov())
loop.create_task(calc())
loop.create_task(updateWebClients())

# root route
@app.route('/')
async def index(request):
    print('index')
    return send_file('html/index.html')

@app.route('/ws')
@with_websocket
async def getMessage(request, ws):
    addr = ws.request.client_addr
    print('updater start', addr)
    connections[addr] = ws
    await sendUpdate(addr, json.dumps(webState))	#inital update

    while True:
        msg = await ws.receive()
        try:
            data = json.loads(msg)
            print(json.dumps(data))
            onUpdate(data)       
        except ValueError:
            pass
        print('received', msg)

# Static CSS/JSS
@app.route("/<path:path>")
async def static(request, path):
    file = 'html/' + path
    if ".." in file:
         return "Not found", 404
    try:
        os.stat(file)
    except:
        return "Not found", 404
    return send_file(file)

if __name__ == "__main__":
    try:
        app.run(debug=1)
    except KeyboardInterrupt:
        pass