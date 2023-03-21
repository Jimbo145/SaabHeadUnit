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

    # with can.Bus(  # type: ignore
    #         channel=can_channel, bustype="socketcan", receive_own_messages=False
    # ) as bus:
    #     # await asyncio.wait_for(send_message(bus, "0x300", bytearray([0x0, 0x90])), timeout=0.5)
    #     await asyncio.sleep(0.1)
    #     await asyncio.wait_for(send_message(bus, "0x290", bytearray([0x00, 0x00, 0x19, 0x09, 0x00])), timeout=0.5)
    #     await asyncio.sleep(0.1)
    #     await asyncio.wait_for(send_message(bus, "0x290", bytearray([0x00, 0x00, 0x19, 0x00, 0x00])), timeout=0.5)
    #     await asyncio.sleep(0.1)
    #     await asyncio.wait_for(send_message(bus, "0x290", bytearray([0x00, 0x00, 0x19, 0x09, 0x00])), timeout=0.5)
    #     await asyncio.sleep(0.1)
    #     await asyncio.wait_for(send_message(bus, "0x290", bytearray([0x00, 0x00, 0x19, 0x00, 0x00])), timeout=0.5)

    internet_timeout = 0
    internet_connected = False
    while not internet_connected:
        result = subprocess.run(['ping', '8.8.8.8', '-c', '1'])
        if result.returncode == 0:
            internet_connected = True
        else:
            internet_timeout += 1

        if internet_timeout == 100:
            break

        await asyncio.sleep(0.1)

    if internet_connected:
        clone_success = subprocess.call(
            ['sudo', 'git', 'clone', 'https://github.com/Jimbo145/SaabHeadUnit.git', '/usr/local/bin/SaabHeadUnitUpdater'])
        if clone_success == 128 and result.stderr == 'fatal: destination path \'SaabHeadUnit\' already exists and is not an empty directory.\\n':
            # git did not clone, attempt pull
            try:
                os.chdir('/usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit')
                subprocess.call(['sudo', 'git', 'reset', '--hard'])
                subprocess.call(['sudo', 'git', 'clean', '-fq'])
                result = subprocess.run(['sudo', 'git', 'pull'], capture_output=True, text=True)
                if result.stdout != 'Already up to date.\\n' and result.stderr == '':
                    # create an update request file
                    subprocess.call(['touch', '/usr/local/bin/SaabHeadUnitUpdater/updated'])
                    pass
            except FileNotFoundError:
                print(' SaabHeadUnit not found')
            except:
                pass

        if os.path.exists('/usr/local/bin/SaabHeadUnitUpdater/update'):
            subprocess.call(['sudo', 'cp', '/usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit/saabCan.py', '/usr/local/bin/SaabHeadUnit/saabCan.py'])
            # copy saabupdate over so it too can be updated via saabCan
            subprocess.call(['sudo', 'cp', '/usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit/saabUpdate.py',
                             '/usr/local/bin/SaabHeadUnit/saabUpdate.py'])

    subprocess.call(['sudo', 'systemctl', 'start', 'saab.service'])


        
        

        



try:
    if __name__ == "__main__":
        
        print("Starting...")
        asyncio.run(main())
except KeyboardInterrupt:
    print("Stopping...")