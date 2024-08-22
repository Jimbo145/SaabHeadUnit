import asyncio
import logging
from typing import List
import subprocess
import can
from can.notifier import MessageRecipient
from enum import Enum
from functools import *
import sys
import time
import shutil
import os
import mimetypes
import gpiozero
import json

from systemd import journal
# import sqlite3
from aiohttp import web
from aiohttp import WSMessage
# import sqlite3          #pip install sqlite3
# from aiohttp import web #pip install aiohttp
    #pip install pyzmq

x_not_available = True
while x_not_available:
    try:
        from pynput.keyboard import Key, Controller
    except Exception as e:
        print(e)
        pass
    else:
        print('pynput connected')
        x_not_available = False
keyboard = Controller()
log = logging.getLogger('saabLog')


messageStore = {}
LogChange: bool = True

global turnSignalAsync
global keyboardPressed
global turn_timer_start
global database
global source_changed
global updated
global test
global gpio_manager
global app_status

updated = False
keyboardPressed = 'None'
firstRun = True
notifier = None
app_data = {
    "par": {
        "scrn_brightness" : 100,
        "led_brightness" : 100,
        "fog_light" : 0

    },
    "status": {
        "battery_voltage": 0,
        "output_current": 0
    }
}

class TurnSignal(Enum):
    OFF = 0
    LEFT = 1
    RIGHT = 2

class GPIOManager:
    def __init__(self):
        self.pin_mapping = {
            'AMFM': gpiozero.DigitalOutputDevice(pin= 'GPIO26', active_high=True, initial_value=False),
            'SCAN': gpiozero.DigitalOutputDevice(pin= 'GPIO21', active_high=True, initial_value=False),
            'CD': gpiozero.DigitalOutputDevice(pin= 'GPIO20', active_high=True, initial_value=False),
            'scrn_brightness': gpiozero.PWMOutputDevice(pin= 'GPIO13', active_high=True, initial_value=0),
        }

    def set_gpio(self, gpio_pin: str, status: bool):
        if status:
            self.pin_mapping[gpio_pin].on()
        else:
            self.pin_mapping[gpio_pin].off()

    def set_pwm(self, gpio_pin: str, brightness: float):
            if brightness > 1 or brightness < 0 or gpio_pin == "":
                return
            self.pin_mapping[gpio_pin].value = brightness
    
    def blink_gpio(self, gpio_pin: str, duration: float):
        if duration < 0 or gpio_pin == "":
            return
        self.pin_mapping[gpio_pin].blink(on_time=duration, off_time=duration, n=1)

    def toggle_gpio(self, gpio_pin: str):
        if self.pin_mapping[gpio_pin].value:
            self.pin_mapping[gpio_pin].off()
        else:
            self.pin_mapping[gpio_pin].on()


gpio_manager: GPIOManager = GPIOManager()


last_turn_signal: TurnSignal = TurnSignal.OFF

home_dir_expanded = os.path.expanduser('~')
log_file = home_dir_expanded + '/saabCan.log'
logging.basicConfig(filename=log_file, level=logging.DEBUG)

async def handle(request):
    file_path = '/home/pi/SaabHeadUnit/saab-control/webserver/index.html'  # Replace this with the actual file path

    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
    except FileNotFoundError:
        return web.Response(status=404, text="File not found")

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'text/html'  # Fallback MIME type if extension is not recognized

    return web.Response(body=file_content, content_type=mime_type)

async def handle_file(request):
    # Assuming you want to serve a specific file, adjust the file path accordingly
    file_path = '/path/to/your/file.txt'  # Replace this with the actual file path

    try:
        with open(log_file, 'rb') as f:
            file_content = f.read()
    except FileNotFoundError:
        return web.Response(status=404, text="File not found")

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/txt'  # Fallback MIME type if extension is not recognized

    return web.Response(body=file_content, content_type=mime_type)

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            if msg.data == 'close':
                await ws.close()
            else:
                log.info(f"Received: {msg.data}")
                response = handle_wsmessage(msg)
                await ws.send_str(f"{response}")
        elif msg.type == web.WSMsgType.ERROR:
            log.error('WebSocket connection closed with exception %s' % ws.exception())

    return ws

def handle_wsmessage(msg: WSMessage) -> str:  
    global app_data
    global gpio_manager
    wsjson = json.loads(msg.data)
    response = {
        "status": 501,
        "group": "",
        "data" : {}
    }
    if wsjson['group'] == 'gpio':
        response['status'] = 200
        response['group'] = 'gpio'
        if wsjson['command'] == 'press':
            gpio_manager.blink_gpio(wsjson['data'], 1.0)
        elif wsjson['command'] == 'toggle':
            pass
        elif wsjson['command'] == 'set':
            pwm_value = float(wsjson['data']['val'])
            gpio_manager.set_pwm(wsjson['data']['pin'], pwm_value)
            set_setting(wsjson['data']['pin'], pwm_value)
            response['data'] = app_data
        elif wsjson['command'] == 'clear':
            pass
    elif wsjson['group'] == 'can':
        response['status'] = 200
        response['group'] = 'can'
        if wsjson['command'] == 'send':
            pass
        elif wsjson['command'] == 'read':
            pass
    elif wsjson['group'] == 'toggle':
        response['status'] = 200
        response['group'] = 'toggle'
        response['data'] = app_data
        if wsjson['command'] == 'press':
            if app_data['par'][wsjson['data']] == 1:
                set_setting(wsjson['data'], 0)
            else:
                set_setting(wsjson['data'], 1)
    elif wsjson['group'] == 'update':
        response['status'] = 200
        response['group'] = 'update'
        response['data'] = app_data
    return json.dumps(response)



app = web.Application()
app.add_routes([web.get('/', handle),
                web.get('/log', handle_file),
                web.get('/ws', websocket_handler)])


def log_subprocess_result(result):
    if result.stdout != '':
        log.debug("Subprocess Result " + str(result.stdout))
        return 0
    else:
        log.error("Subprocess Result " + str(result.stderr)) 
        return -1


def hex_to_int(hex_num: str) -> int:
    return int(hex_num, 16)

def set_setting(key, value):
    global app_data
    app_data['par'][key] = value
    write_settings()


def read_settings():
    global app_data
    settings_path = "/home/pi/SaabHeadUnit/saab-control/settings.json"
    try:
        with open(settings_path, 'r') as file:
            content = file.read()
            app_data['par'] = json.loads(content)
    except FileNotFoundError:
        log.error(f"File not found: {settings_path}")
        return ""
    finally:
        file.close()

def write_settings():
    global app_data
    settings_path = "/home/pi/SaabHeadUnit/saab-control/settings.json"
    try:
        with open(settings_path, 'w') as file:
            json.dump(app_data['par'], file)
    except FileNotFoundError:
        log.error(f"File not found: {settings_path}")
    finally:
        file.close()


def receive_message(msg: can.Message, bus: can.bus) -> None:
    """Regular callback function. Can also be a coroutine."""
    global firestore_connected
    byteList = []
    for byt in msg.data:
        byteList.append(hex_to_int(hex(byt)))

    # print(BitArray(msg.data).unpack(hex))
    try:
        if bytearray(messageStore[msg.arbitration_id]) != msg.data:
            # BitArray(bytes=messageStore[msg.arbitration_id]).pp('bin', show_offset=False)
            # BitArray(bytes=msg.data).pp('bin', show_offset=False)
            log.debug(f"Message recieve : {hex(msg.arbitration_id)} {byteList} {msg.dlc}")
    except KeyError:
        log.debug(f"New Message : {hex(msg.arbitration_id)} {byteList} {msg.dlc}")


    messageStore.update({msg.arbitration_id: byteList})
    parseMessage(msg.arbitration_id, byteList, bus)


def parseMessage(can_id: int, data: List[int], bus: can.Bus):
    global keyboardPressed
    global turnSignalAsync
    global source_changed
    global last_turn_signal
    global turn_timer_start

    if can_id == hex_to_int("0x60"):
        """Voltage:
            ex: 0x60,0x3(length),0x0,0xa0,0x69(voltage) -> 0x69*135 = 14175 /1000 = 14.1 V"""

        voltage = ((data[2]) * 135) / 1000
        log.debug(f'Car Battery voltage {voltage}')
    elif can_id == hex_to_int("0x70"):
        """ Unknown 5 bytes
        """
        pass
    elif can_id == hex_to_int("0x90"):
        """ Unknown 1 bytes
        """
        pass
    elif can_id == hex_to_int("0x91"):
        """ - b2
                - 00000000 (0x00) GUESS Cruise control not setup / brake must be pressed
                - 00100000 (0x20) Brake released, cruise control enabled?
                - 10100000 (0xa0) Brake pressed
            - b1
                - 00000000 (00) Cruise control on
                - 00100000 (20) Cruise control off"""
        pass
    elif can_id == hex_to_int("0x108"):
        """ Gauge Cluster
            - b0
                00 to FF Accelerator Position
            - b1
                - turbo boost ?
            - b2:b3
                - 16 bit integer for RPM
            - b4:b5
                - 16 bit integer for 
        """
        pass
    elif can_id == hex_to_int("0x130"):
        """ unknown
            1 byte 
        """
        pass
    elif can_id == hex_to_int("0x135"):
        """ unknown
            1 byte 
        """
        pass
    elif can_id == hex_to_int("0x140"):
        """ Unknown 5 bytes
        """
        pass
    elif can_id == hex_to_int("0x143"):
        """ Windshield Wiper Trigger
            [0] to ack wiper start?
            [64] Rain sensing maybe?
        """
        pass
    elif can_id == hex_to_int("0x144"):
        """ Windshield Wiper Trigger
            [1] to start wiper
            [0] to ack 143's [64]
        """
        pass
    elif can_id == hex_to_int("0x150"):
        """ unknown
            1 byte 
        """
        pass
    elif can_id == hex_to_int("0x160"):
        """ Unknown 5 bytes
        """
        pass
    elif can_id == hex_to_int("0x170"):
        """ Coolant Temp
            b1 - 0x28 = Temp (C)
        """
        pass
    elif can_id == hex_to_int("0x180"):
        """ Parking Sensor Raw (PDC)
            - b1
            - b2
            - b3
        """
        log.debug(f'Parking Sensor (PDC) {data}')
        pass
    elif can_id == hex_to_int("0x183"):
        """ Parking Sensor (SPA)
            - b0
                - (67) SPA Not Active
                - (98) SPA Active
            - b3
                - SPA Distance
        """
        log.debug(f'Parking Sensor (SPA) {data}')
        pass
    elif can_id == hex_to_int("0x190"):
        """ Unknown
        """
        pass
    elif can_id == hex_to_int("0x210"):
        """ Seatbelts
        """
        pass
    elif can_id == hex_to_int("0x211"):
        """ Hazard Lights"""
        pass
    elif can_id == hex_to_int("0x220"):
        """ - b1:b2
                - Steering wheel angle (16 bit special integer)
                - When MSB is 0, decode as regular 16 bit integer (b1 << 8) + b2.
                - When MSB is 1, subtract 65536 from (b1 << 8), before adding with b2.
                - This results in a range of ~-8600 to ~+8600 representing full wheel range (lock to lock).
                - Unsure what the real-world angle-equivalent of this value is (yet)."""
        pass
    elif can_id == hex_to_int("0x230"):
        """ keyfob
            - b0
                - (10)
            - b1
                - (0x40) Lock
                - (0xC0) Long Press Lock
                - (0x10) Unlock
                - (0x01) Hello On (Dash on remote)
                - (0x02) Hello Off (Dash on remote)
                - (0x03) Hello Long Press
                - (0x04) Trunk
                - (0x0C) Long Press Trunk
        """
        pass

    elif can_id == hex_to_int("0x290"):
        """- b0
                - 00000001 (01) Windshield washer (pull stick fully in)
                - 00000100 (04) Horn
                - 00010000 (08) Flash high beams (pull stick halfway)
                - 00011000 (24) Toggle high beams (pull stick fully in)
            - b1
                - 00000001 (01) Wiper single
                - 00001010 (10) Wiper intermittent
                - 00001011 (11) Wiper slow
                - 00001101 (13) Wiper fast
            - b2
                - 00000001 (01) ESP Button
            - b3
                - 00000000 (00) Default
                - 00000001 (01) Volume UP
                - 00000010 (02) Volume DOWN
                - 00000011 (03) SRC button
                - 00000100 (04) Voice activation button
                - 00000101 (05) Seek forward
                - 00000110 (06) Seek backward
                - 00010001 (11) NXT button
                - 00010010 (18) Phone button
            - b4
                - 00000000 (00) Default
                - 00000100 (4) Indicator right
                - 00001000 (8) Indicator left
        """
        log.info(f"Handle: 0x290 {data} ")

        if not source_changed:
            asyncio.create_task(handle_source_change(bus))
            source_changed = True

        # b3

        if data[3] == 00:
            # all buttons up
            if keyboardPressed == 'M':
                keyboard.release('M')
            if keyboardPressed == 'V':
                keyboard.release('V')
            if keyboardPressed == 'N':
                keyboard.release('N')
            if keyboardPressed == 'H':
                keyboard.release('H')
            if keyboardPressed == 'P':
                keyboard.release('P')
            keyboardPressed = 'None'
        elif data[3] == 4:
            keyboard.press('M')
            keyboardPressed = 'M'
            log.info('Keyboard: "M" -  OpenAuto: "Voice assist"')
        elif data[3] == 6:
            keyboard.press('V')
            keyboardPressed = 'V'
            log.info('Keyboard: "V" -  OpenAuto: "Previous track"')
        elif data[3] == 5:
            keyboard.press('N')
            keyboardPressed = 'N'
            log.info('Keyboard: "N" -  OpenAuto: "Next track"')
        elif data[3] == 17:
            keyboard.press('H')
            keyboardPressed = 'H'
            log.info('Keyboard: "H" -  OpenAuto: "Home"')
        elif data[3] == 18:
            keyboard.press('P')
            keyboardPressed = 'P'
            log.info('Keyboard: "P" -  OpenAuto: "Answer call/Phone menu')
        else:
            pass
        # b4
        if data[4] == 0:
            # send turn signal 2x times if last was true;
            log.info(f"Turn Signal Off ")
            if last_turn_signal != TurnSignal.OFF and (time.monotonic() - turn_timer_start) < 1:
                log.info(f"{time.monotonic() - turn_timer_start}")

                turnSignalAsync = asyncio.create_task(handle_turn_signal(last_turn_signal, bus))
                turn_timer_start = 0

            last_turn_signal = TurnSignal.OFF
        elif data[4] == 128:

            if last_turn_signal != TurnSignal.RIGHT:
                last_turn_signal = TurnSignal.RIGHT
                if turnSignalAsync is not None:
                    turnSignalAsync.cancel()
                turn_timer_start = time.monotonic()
                log.info(f"Turn Signal Right {turn_timer_start}")
        elif data[4] == 64:
            if last_turn_signal != TurnSignal.LEFT:
                last_turn_signal = TurnSignal.LEFT
                if turnSignalAsync is not None:
                    turnSignalAsync.cancel()

                turn_timer_start = time.monotonic()
                log.info(f"Turn Signal Left {turn_timer_start}")
    elif can_id == hex_to_int("0x300"):
        """
            - b0
                - (00) lights Off
                - (08) Lights Off and park brake
                - (20) Corner Lights
                - (10) Main Lights
                - +80 Fog Lights
                - +40 Rear Fog lgihts
                - (A0) Coner pluh front fog
                - +8 Parking brake
        """
        pass
    elif can_id == hex_to_int("0x310"):
        """ 
            - b0 
                - 00000000 (00) Full Anti-theft
                - 00001000 (06) Doors Only Anti-theft
            - b1
                - SID-C
                - 00000000 (00) OFF
                - 00000001 (01) ESP Pressed
                - 00000010 (02) Window Defrost Manual
                - 00000100 (04) SPA on
            - b3
                AC Fan
                - 00000000 (00) Middle Speed Interior Fan
                - 00000100 (04) High speed Fan
                - 00010000 (10) Low Speed 
                - 01000000 (40) AC Auto 
            - b4 
                Seat Heat
                - (10) Seat Heater Auto
                - (50) Seat Heater Manual
            - b5
                - SID-C
                - 00000000 (00) OFF
                - 00100000 (20) ON (Toggle)
                - 00000000 (80) Long Press CLR
        """
        pass
    elif can_id == hex_to_int("0x320"):
        """ - b0
                Locking status / controls 
                - 00010000 (10) Driver unlocked
                - 00010001 (11) Driver locked
                - 00010100 (14) Unlock Button
                - 00011001 (19) Lock Button
            - b1
                - Mirror adjustment, triggered by d-pad
                - 00000000 (00) Default
                - 10000000 (80) Adjustment in progress
            - b3
                - Mirror adjust DPAD direction left mirror
                - 00010000 (10) LEFT
                - 00100000 (20) RIGHT
                - 01000000 (40) DOWN
                - 10000000 (80) UP
            - b4
                - Mirror adjust DPAD direction Right Mirror
                - 00010000 (10) LEFT
                - 00100000 (20) RIGHT
                - 01000000 (40) DOWN
                - 10000000 (80) UP
            - b6
                Front Windows
                - 00000010   passenger window up button
                - 00000100   passenger window down button
                - 00001000   passenger comfort open button
                - 00010000   driver window in motion 
                - 00100000   driver window closed
                - 10000000   window lock button  
            - b7
                Rear Windows
                - 00000100   passenger window down button
                - 00001000   passenger window up button
                - 00010000   passenger comfort open button
                - 00100000   driver up button 
                - 01000000   driver down button  
                - 10000000   driver comfort open button
            - """
        pass
    elif can_id == hex_to_int("0x330"):
        """ Unknown 5 bytes
        """
        pass
    elif can_id == hex_to_int("0x340"):
        """ unknown
            6 byte 
        """
        pass
    elif can_id == hex_to_int("0x350"):
        """ Unknown 5 bytes
        """
        pass
    elif can_id == hex_to_int("0x370"):
        """ - b0
                - Front fog lights / reversing light
                - 00000000 (00) OFF
                - 00000001 (01) REVERSE
                - 01000000 (40) ON
                - 01000001 (41) ON and REVERSE
            - b1 
                - 00000000 (00) Normal
                -          (80) Dash Board Lights
        """
        pass
    elif can_id == hex_to_int("0x380"):
        """ - b0
                - Brakes pressesd
                - 00000000 (00) Default
                - 00100000 (20) Brakes pressed
            - b1
                - Rear fog lights
                - 00000000 (00) OFF
                - 00100000 (20) ON
        """
        pass
    elif can_id == hex_to_int("0x390"):
        """  - Normal state
                - 0x00 0x00 
             - Beep state
                - 0x00 0x80"""
        pass
    elif can_id == hex_to_int("0x400"):
        """ Unknown 5 bytes
        """
        pass
    elif can_id == hex_to_int("0x430"):
        """ unknown
            2 byte 
        """
        pass
    elif can_id == hex_to_int("0x440"):
        """ unknown
            1 byte 
        """
        pass
    elif can_id == hex_to_int("0x445"):
        """ Temp Outside (C)
            (b1 - b2) / 2 = Temp C
        """
        pass
    elif can_id == hex_to_int("0x450"):
        """ Unknown  bytes
        """
        pass
    elif can_id == hex_to_int("0x460"):
        """- b0
                - 00000000 (00) Night mode off
                - 01000000 (64) Night mode on
            - b1:b2
                - Instrument lighting brightness levels 
                - Night mode brightness
                - Two independant 8 bit integers
            - b3:b4
                - Brightness sensor
                - 16 bit integer
        """
        brightness_adjusted = 100.0
        brightness_sensor = (data[3] << 8) + data[4]
        sensor_percent = 1.0 * (brightness_sensor / 65535.0)
        instrument_brightness = 1.0 * (data[1] / 255.0)

        brightness_adjusted = brightness_adjusted * sensor_percent

        instrumentLightLevel = data[1]
        if data[0] == 64:
            nightModeOn = True
        else:
            nightModeOn = False
        log.debug(f"Handle 0x460 (light level) {brightness_adjusted}")
    elif can_id == hex_to_int("0x480"):
        """  Unknown  2 bytes
        """
        pass
    elif can_id == hex_to_int("0x490"):
        """ Unknown 8 bytes
        """
        pass
    elif can_id == hex_to_int("0x520"):
        """ - b0
                - Years after 2000
                - 8 bit int
            - b1
                - Month
                - 8 bit int
            - b2
                - Day
                - 8 bit int
            - b3
                - Hour
                - 8 bit int
            - b4
                - Minute
                - 8 bit int
            - b5
                - Second
                - 8 bit int"""
        pass
    elif can_id == hex_to_int("0x532"):
        """ Unknown 5 bytes
        """
        pass
    elif can_id == hex_to_int("0x535"):
        """ unknown
            4 byte 
        """
        pass
    elif can_id == hex_to_int("0x545"):
        """ Indoor Temp?
            -b0 0x5 
            -b1 high byte
            -b2 low byte
            
            ((b1<<8)+b2)/10 = Temp (C)
        """
        pass
    elif can_id == hex_to_int("0x621"):
        """ unknown
            8 byte 
        """
        pass
    elif can_id == hex_to_int("0x625"):
        """ unknown
            8 byte 
        """
        pass
    elif can_id == hex_to_int("0x627"):
        """ Unknown 5 bytes
        """
        pass
    elif can_id == hex_to_int("0x690"):
        """ unknown
            8 byte 
        """
        pass
    elif can_id == hex_to_int("0x62A"):
        """ Unknown 5 bytes
        """
        pass
    elif can_id == hex_to_int("0x700"):
        """ unknown
            8 byte 
        """
        pass
    elif can_id == hex_to_int("0x740"):
        # unsure what this is
        pass
    # elif canid == int("0x627", 16):
    # print(data[0])
    else:
        log.info(f"Handle unsupported {can_id} {data}")


async def send_message(bus: can.Bus,can_id: str, data:bytearray):
    message = can.Message(arbitration_id=hex_to_int(can_id), data=data, is_extended_id=False)
    try:
        bus.send(message)
        bus.flush_tx_buffer()
        log.info(f"Message {message} sent on {bus.channel_info}")
    except can.CanError as e:
        log.info(f"Message NOT sent {e.args}")


async def get_battery_status():
    global app_data
    result = subprocess.run(['lifepo4wered-cli' , 'get', 'vbat'], check=True, text=True, capture_output=True)

    output = result.stdout.strip()
    try:
        battery_voltage = float(output)
        app_data['status']['battery_voltage'] = battery_voltage
    except ValueError:
        log.warning(f"Life4powered voltage Failed to parse numeric value from output {output}")

    result = subprocess.run(['lifepo4wered-cli' , 'get', 'IOUT'], check=True, text=True, capture_output=True)

    output = result.stdout.strip()
    try:
        output_current = float(output)
        app_data['status']['output_current'] = output_current
    except ValueError:
        log.warning(f"Life4powered Current Failed to parse numeric value from output {output}")


    await asyncio.sleep(10)
    asyncio.create_task(get_battery_status())


def setup_can(test_mode):
    # ip link set can0 up type can bitrate 33300
    can_chanel = 'can0'
    if test_mode:
        result = subprocess.run(['sudo', 'modprobe', 'vcan'], 
                                text=True, 
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.STDOUT)
        log_subprocess_result(result)
        result = subprocess.run(['sudo', 'ip', 'link', 'add', 'dev', 'vcan0', 'type', 'vcan'], 
                                text=True, 
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.STDOUT)
        log_subprocess_result(result)
        result = subprocess.run(['sudo', 'ip', 'link', 'set', 'up', 'vcan0'], 
                                text=True, 
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.STDOUT)
        log_subprocess_result(result)
        can_chanel = 'vcan0'

    result = subprocess.run(['sudo', 'ip', 'link', 'set', can_chanel, 'up', 'type', 'can', 'bitrate', '33300'], 
                            text=True, 
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.STDOUT)
    log_subprocess_result(result)

    return can_chanel


async def handle_turn_signal(signal: TurnSignal, bus: can.Bus) -> None:
    step_count = 4

    if signal == TurnSignal.RIGHT:
        signal_data = hex_to_int("0x80")
    elif signal == TurnSignal.LEFT:
        signal_data = hex_to_int("0x40")
    else:
        log.warning("unexpected handle turn signal")
        return

    for i in range(step_count):
        await asyncio.sleep(0.35)
        last_message = messageStore[hex_to_int("0x290")]
        if i % 2 == 0:
            # even
            last_message[4] = signal_data
        elif i % 2 == 1:
            # odd
            last_message[4] = 0

        await (send_message(bus, "0x290", last_message))


async def handle_source_change(bus: can.Bus) -> None:
    global source_changed
    source_changed = True
    last_message = messageStore[hex_to_int("0x290")]
    last_message[3] = 3
    # this is loop unrolled
    await (send_message(bus, "0x290", last_message))
    await asyncio.sleep(0.5)
    last_message[3] = 0
    await (send_message(bus, "0x290", last_message))
    await asyncio.sleep(3.0)
    last_message[3] = 3
    await (send_message(bus, "0x290", last_message))
    await asyncio.sleep(0.5)
    last_message[3] = 0
    await (send_message(bus, "0x290", last_message))


async def handle_beep(bus: can.Bus, num: int) -> None:
    """t("0x390"):
         - Normal state
                - 0x00 0x00
             - Beep state
                - 0x00 0x80
    """
    for x in range(num):
        await (send_message(bus, "0x390", [hex_to_int("0x00"), hex_to_int("0x80")]))
        await asyncio.sleep(0.5)
        await (send_message(bus, "0x390", [hex_to_int("0x00"), hex_to_int("0x00")]))
        await asyncio.sleep(0.5)


async def main(test_mode) -> None:
    """The main function that runs in the loop."""
    global notifier
    global turn_timer_start
    global turnSignalAsync
    global updated
    global last_turn_signal

    turn_timer_start = 0
    turnSignalAsync = None
    last_turn_signal = TurnSignal.OFF

    read_settings()

    can_channel = setup_can(test_mode)

    app_runner = web.AppRunner(app)
    await app_runner.setup()
    site = web.TCPSite(app_runner)
    await site.start()

    with can.Bus(  # type: ignore
            channel=can_channel, bustype="socketcan", receive_own_messages=False
    ) as bus:
        reader = can.AsyncBufferedReader()

        if app_data['par']['fog_light'] == 1:
            await asyncio.wait_for(send_message(bus, "0x300", bytearray([0x0, 0x90])), timeout=0.5)
            bus.flush_tx_buffer()

        if updated:
            asyncio.create_task(handle_beep(bus, 2))
            pass

        receive_part = partial(receive_message, bus=bus)

        listeners: List[MessageRecipient] = [
            receive_part,  # Callback function
            reader,  # AsyncBufferedReader() listener
        ]
        # Create Notifier with an explicit loop to use for scheduling of callbacks
        loop = asyncio.get_running_loop()
        notifier = can.Notifier(bus, listeners, loop=loop)

        asyncio.create_task(get_battery_status())

        while True:
            # Wait for next message from AsyncBufferedReader
            msg = await reader.get_message()


            await asyncio.sleep(0.1)



try:
    if __name__ == "__main__":

        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        log.addHandler(sh)
        log.setLevel(logging.INFO)
        log.info("Starting SaabCan...")        


        source_changed = False

        if os.path.exists('/usr/local/bin/SaabHeadUnitUpdater/update'):
            result1 = subprocess.run(['sudo', 'cp', '/usr/local/bin/SaabHeadUnit/saabUpdate.py',
                            '/usr/local/bin/SaabHeadUnitUpdater/saabUpdate.py'], capture_output=True, text=True)
            log_subprocess_result(result1)
            result2 = subprocess.run(['sudo', 'rm', '/usr/local/bin/SaabHeadUnitUpdater/update'], capture_output=True, text=True)
            log_subprocess_result(result2)
            log.info('update complete')
            updated = True



        args = sys.argv[1:]

        if len(args) > 0 and args[0] == "test":
            log.info ("Test Mode")
            test = True
        else:
            test = False



        asyncio.run(main(test))

except KeyboardInterrupt:
    print("Stopping...")
    #notifier.stop()
