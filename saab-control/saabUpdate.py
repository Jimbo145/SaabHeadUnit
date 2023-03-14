import subprocess
import asyncio
import can


async def send_message(bus: can.Bus,can_id: str, data:bytearray):
    message = can.Message(arbitration_id=int(can_id, 16), data=data, is_extended_id=False)
    try:
        bus.send(message)
    except can.CanError:
        pass

async def main() -> None:

    """The main function that runs in the loop."""
    try:
        result = subprocess.run(['sudo', 'ip', 'link', 'set', 'can0', 'up', 'type', 'can', 'bitrate', '33300'])
    except:
        pass

    can_channel = "can0"

    with can.Bus(  # type: ignore
            channel=can_channel, bustype="socketcan", receive_own_messages=False
    ) as bus:
        await asyncio.wait_for(send_message(bus, "0x300", bytearray([0x0, 0x90])), timeout=0.5)
        await asyncio.wait_for(send_message(bus, "0x290", bytearray([0x0, 0x0, 0x9, 0x0])), timeout=0.5)
        await asyncio.sleep(0.1)
        await asyncio.wait_for(send_message(bus, "0x290", bytearray([0x0, 0x0, 0x0, 0x0])), timeout=0.5)
        await asyncio.sleep(0.1)
        await asyncio.wait_for(send_message(bus, "0x290", bytearray([0x0, 0x0, 0x9, 0x0])), timeout=0.5)
        await asyncio.sleep(0.1)
        await asyncio.wait_for(send_message(bus, "0x290", bytearray([0x0, 0x0, 0x0, 0x0])), timeout=0.5)
        await asyncio.sleep(0.1)

    internet_connected = False
    while not internet_connected:
        result = subprocess.run(['ping', '8.8.8.8', '-c', '1'])
        if result.returncode == 0:
            internet_connected = True
        await asyncio.sleep(0.1)
    
        # Wait for next message from AsyncBufferedReader


    result = subprocess.call(['rm', '-rf', '/usr/local/bin/SaabHeadUnit'])
    print(result)
    subprocess.call(['sudo', 'git', 'clone', 'https://github.com/Jimbo145/SaabHeadUnit.git', '/usr/local/bin/SaabHeadUnit'])

    subprocess.call(["python3", "/usr/local/bin/SaabHeadUnit/saab-control/saabCan.py"])
        
        

        



try:
    if __name__ == "__main__":
        
        print("Starting...")
        asyncio.run(main())
except KeyboardInterrupt:
    print("Stopping...")