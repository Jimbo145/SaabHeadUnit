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
from systemd import journal
# import sqlite3
# from aiohttp import web
# import sqlite3          #pip install sqlite3
# from aiohttp import web #pip install aiohttp
    #pip install pyzmq

x_not_available = True
while x_not_available:
    try:
        from pynput.keyboard import Key, Controller
    except:
        pass
    else:
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


class TurnSignal(Enum):
    OFF = 0
    LEFT = 1
    RIGHT = 2

DATABASE_FILE = 'database.db'


last_turn_signal: TurnSignal = TurnSignal.OFF

logging.basicConfig(filename='/tmp/can.log', level=logging.DEBUG)


# logging.basicConfig(encoding='utf-8', level=logging.INFO)

def log_subprocess_result(result):
    if result.stdout != '':
        log.info(result.stdout)
        return 0
    else:
        log.error(result.stderr)
        return -1



def hex_to_int(hex_num: str) -> int:
    return int(hex_num, 16)

# def create_database_file():
#     if not os.path.exists(DATABASE_FILE):
#         conn = sqlite3.connect(DATABASE_FILE)
#         conn.close()

# function to create database table if it doesn't exist
# def create_database_table():
#     conn = sqlite3.connect(DATABASE_FILE)
#     conn.execute('''
#     CREATE TABLE IF NOT EXISTS mytable (
#         id INTEGER PRIMARY KEY,
#         data INTEGER
#     );
#     ''')
#     conn.close()

# def set_data(id, data):
#     conn = sqlite3.connect(DATABASE_FILE)
#     cursor = conn.execute(f"SELECT id FROM mytable WHERE id={id}")
#     existing_data = cursor.fetchone()
#     if existing_data:
#         conn.execute(f"UPDATE mytable SET data={data} WHERE id={id}")
#     else:
#         conn.execute(f"INSERT INTO mytable (id, data) VALUES ({id}, {data})")
#     conn.commit()
#     conn.close()


def receive_message(msg: can.Message, bus: can.bus) -> None:
    """Regular callback function. Can also be a coroutine."""

    byteList = []
    for byt in msg.data:
        byteList.append(hex_to_int(hex(byt)))

    # print(BitArray(msg.data).unpack(hex))
    try:
        if messageStore[msg.arbitration_id] != msg.data:
            # BitArray(bytes=messageStore[msg.arbitration_id]).pp('bin', show_offset=False)
            # BitArray(bytes=msg.data).pp('bin', show_offset=False)
            log.debug(f"Message : {hex(msg.arbitration_id)} {byteList} {msg.dlc}")
    except KeyError:
        log.debug(f"New Message : {hex(msg.arbitration_id)} {byteList} {msg.dlc}")

    messageStore.update({msg.arbitration_id: byteList})
    parseMessage(msg.arbitration_id, byteList, bus)


def parseMessage(can_id: int, data: List[int], bus: can.Bus):
    global keyboardPressed
    global turnSignalAsync
    global source_changed
    
    if can_id == hex_to_int("0x60"):
        """Voltage:
            ex: 0x60,0x3(length),0x0,0xa0,0x69(voltage) -> 0x69*135 = 14175 /1000 = 14.1 V"""

        voltage = ((data[2]) * 135) / 1000
        log.debug(f'Car Battery voltage {voltage}')
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
            - b3
                - 00000000 (00) Default
                - 00000001 (01) Volume UP
                - 00000010 (02) Volume DOWN
                - 00000011 (03) SRC button
                - 00000100 (04) Voice activation button
                - 00000101 (05) Seek forward
                - 00000110 (06) Seek backward
                - 00010001 (09) NXT button
                - 00010010 (12) Phone button
            - b4
                - 00000000 (00) Default
                - 00000100 (4) Indicator right
                - 00001000 (8) Indicator left
        """
        log.info(f"Handle: 0x290 b0:{data[0]} b1:{data[1]} b3:{data[3]} b4:{data[4]}")

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
        elif data[3] == 9:
            keyboard.press('H')
            keyboardPressed = 'H'
            log.info('Keyboard: "H" -  OpenAuto: "Home"')
        elif data[3] == 12:
            keyboard.press('P')
            keyboardPressed = 'P'
            log.info('Keyboard: "P" -  OpenAuto: "Answer call/Phone menu')
        # b4
        if data[4] == (0):
            # send turn signal 2x times if last was true;
            global last_turn_signal
            global turn_timer_start

            if last_turn_signal != TurnSignal.OFF and (time.monotonic() - turn_timer_start) < 1:
                log.info("Turn Signal Off")
                turnSignalAsync = asyncio.create_task(handle_turn_signal(last_turn_signal, bus))
                turn_timer_start = 0

            last_turn_signal = TurnSignal.OFF
        elif data[4] == (64):
            last_turn_signal = TurnSignal.RIGHT
            if turnSignalAsync is not None:
                turnSignalAsync.cancel()
            turn_timer_start = time.monotonic()
            log.info("Turn Signal Right")
        elif data[4] == (128):
            last_turn_signal = TurnSignal.LEFT
            if turnSignalAsync is not None:
                turnSignalAsync.cancel()
            turn_timer_start = time.monotonic()
            log.info("Turn Signal Left")
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
        brightness_sensor = (data[2] << 8) + data[1]
        log.info(f"Handle 0x460 (light level) {data}")
        instrumentLightLevel = data[1]
        if data[0] == 64:
            nightModeOn = True
        else:
            nightModeOn = False
    elif can_id == hex_to_int("0x740"):
        log.info(f"Handle 0x740 {data}")

    # elif canid == int("0x627", 16):
    # print(data[0])
    # else:
    # print(f"unsupported code: {hex(canid)}")


firstRun = True

notifier = None


async def send_message(bus: can.Bus,can_id: str, data:bytearray):
    message = can.Message(arbitration_id=hex_to_int(can_id), data=data, is_extended_id=False)
    try:
        bus.send(message)
        bus.flush_tx_buffer()
        log.info(f"Message {message} sent on {bus.channel_info}")
    except can.CanError:
        log.info(f"Message NOT sent {can.CanError}")


async def get_battery_status():
    output = subprocess.run(['lifepo4wered-cli' , 'get', 'vbat'], check=True, text=True)
    battery_voltage = float(output.decode().strip())

    log.info("Life4powered voltage: {:.2f} V".format(battery_voltage))
    await asyncio.sleep(10)
    asyncio.create_task(get_battery_status())


def setup_can(test_mode):
    # ip link set can0 up type can bitrate 33300
    can_chanel = 'can0'
    if test_mode:
        result = subprocess.run(['sudo', 'modprobe', 'vcan'], text=True)
        log_subprocess_result(result)
        result = subprocess.run(['sudo', 'ip', 'link', 'add', 'dev', 'vcan0', 'type', 'vcan'], text=True)
        log_subprocess_result(result)
        can_chanel = 'vcan0'

    result = subprocess.run(['sudo', 'ip', 'link', 'set', can_chanel, 'up', 'type', 'can', 'bitrate', '33300'], text=True)
    log_subprocess_result(result)

    return can_chanel


async def handle_turn_signal(signal: TurnSignal, bus: can.Bus) -> None:
    step_count = 4

    if signal == TurnSignal.RIGHT:
        signal_data = hex_to_int("0x40")
    elif signal == TurnSignal.LEFT:
        signal_data = hex_to_int("0x80")
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
    #this is loop unrolled
    await (send_message(bus, "0x290", last_message))
    await asyncio.sleep(0.2)
    last_message[3] = 0
    await (send_message(bus, "0x290", last_message))
    await asyncio.sleep(0.2)
    last_message[3] = 3
    await (send_message(bus, "0x290", last_message))
    await asyncio.sleep(0.2)
    last_message[3] = 0
    await (send_message(bus, "0x290", last_message))
    await asyncio.sleep(0.2)


async def main(test_mode) -> None:
    """The main function that runs in the loop."""
    global notifier
    global turn_timer_start
    global turnSignalAsync


    turn_timer_start = 0
    turnSignalAsync = None

    can_channel = setup_can(test_mode)

    with can.Bus(  # type: ignore
            channel=can_channel, bustype="socketcan", receive_own_messages=False
    ) as bus:
        reader = can.AsyncBufferedReader()

        await asyncio.wait_for(send_message(bus, "0x300", bytearray([0x0, 0x90])), timeout=0.5)
        bus.flush_tx_buffer()


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

# async def get_data_handler(request):
#     id = request.match_info['id']
#     conn = sqlite3.connect(DATABASE_FILE)
#     cursor = conn.execute(f"SELECT data FROM mytable WHERE id={id}")
#     data = cursor.fetchone()
#     if data:
#         conn.close()
#         return web.Response(text=str(data[0]))
#     else:
#         conn.close()
#         return web.Response(text="Data not found", status=404)
# # async def set_data_handler(request):
#     data = await request.json()
#     id = data['id']
#     data = int(data['data'])
#     conn = sqlite3.connect(DATABASE_FILE)
#     conn.execute(f"INSERT INTO mytable (id, data) VALUES ({id}, {data})")
#     conn.commit()
#     conn.close()
#     return web.Response(text="Data inserted successfully")

# app = web.Application()
# app.add_routes([web.get('/data/{id}', get_data_handler)])
# app.add_routes([web.post('/data', set_data_handler)])

try:
    if __name__ == "__main__":
        jh = journal.JournalHandler()
        jh.setLevel(logging.DEBUG)
        log.addHandler(jh)

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



        args = sys.argv[1:]
        
        if len(args) > 0 and args[0] == "test":
            print("Test Mode")
            test = True
        else:
            test = False

        # create_database_file()
        # create_database_table()

        asyncio.run(main(test))
        # web.run_app(app)

except KeyboardInterrupt:
    print("Stopping...")
    #notifier.stop()
