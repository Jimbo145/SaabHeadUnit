import subprocess
import asyncio
import can
import os
from systemd import journal
import logging


logging.basicConfig(filename='/tmp/update.log', level=logging.DEBUG)
log = logging.getLogger('saabUpdateLog')


def log_subprocess_result(result):
    if result.stdout != '':
        log.info(result.stdout)
        return 0
    else:
        log.error(result.stderr)
        return -1


async def send_message(bus: can.Bus,can_id: str, data:bytearray):
    message = can.Message(arbitration_id=int(can_id, 16), data=data, is_extended_id=False)
    try:
        bus.send(message)
    except can.CanError:
        pass


async def copy_files():
    journal.send('Copy Files')
    if os.path.exists('/usr/local/bin/SaabHeadUnitUpdater/update'):
        subprocess.call(['sudo', 'systemctl', 'stop', 'saab.service'])
        log.info('update notifier present, copy files')
        if not os.path.isdir("/usr/local/bin/SaabHeadUnit"):
            result = subprocess.run(
                ['sudo', 'mkdir', '-v', '/usr/local/bin/SaabHeadUnit'], capture_output=True, text=True)
            log.info(result.stdout)

        result5 = subprocess.run(
            ['sudo', 'cp', '-uv', '/usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit/saab-control/saabCan.py',
             '/usr/local/bin/SaabHeadUnit/saabCan.py'], capture_output=True, text=True)
        log.info(result5.stdout)
        # copy saabupdate over so it too can be updated via saabCan
        result6 = subprocess.run(
            ['sudo', 'cp', '-uv', '/usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit/saab-control/saabUpdate.py',
             '/usr/local/bin/SaabHeadUnit/saabUpdate.py'], capture_output=True, text=True)
        log.info(result6.stdout)
        subprocess.call(['sudo', 'systemctl', 'start', 'saab.service'])
        return True
    return False

async def main() -> None:
    """The main function that runs in the loop."""
    # try:
    #    result = subprocess.run(['sudo', 'ip', 'link', 'set', 'can0', 'up', 'type', 'can', 'bitrate', '33300'])
    # except:
    #    pass

    # can_channel = "can0"

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

    # send updates if update request file is there
    update = await copy_files()

    # start service immediately
    subprocess.call(['sudo', 'systemctl', 'start', 'saab.service'])

    internet_timeout = 0
    internet_connected = False

    while not internet_connected:
        result = subprocess.run(['ping', '8.8.8.8', '-c', '1'])
        if result.returncode == 0:
            internet_connected = True
        await asyncio.sleep(0.1)

    if internet_connected:
        log.info("Internet Connected")
        if os.path.isdir("/usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit"):
            try:
                os.chdir('/usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit')
                # log_subprocess_result(subprocess.run(['sudo', 'git', 'reset', '--hard'], capture_output=True, text=True))

                # log_subprocess_result(subprocess.run(['sudo', 'git', 'clean', '-fq'], capture_output=True, text=True))
                gitRevSubprocessResult = subprocess.run(['sudo', 'git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True)
                gitRev = str(gitRevSubprocessResult.stdout)
                log.info(f'Pre pull Revision {gitRev}')
                result3 = subprocess.run(['sudo', 'git', 'pull'], capture_output=True, text=True)
                log_subprocess_result(result3)
                newGitRevSubprocessResult = subprocess.run(['sudo', 'git', 'rev-parse', '--short', 'HEAD'],
                                                        capture_output=True, text=True)
                newGitRev = str(newGitRevSubprocessResult.stdout)
                log.info(f'Post pull Revision {newGitRev}')
                if gitRev == newGitRev:
                    log.info("Repo up to date")
                else:
                    # create an update request file
                    subprocess.run(f'sudo sh -c \'echo "{newGitRev}" > /usr/local/bin/SaabHeadUnitUpdater/update\'', shell=True)
                    log.info("Pull Completed " + result3.stdout)
            except FileNotFoundError:
                log.error('SaabHeadUnit not found')
            except Exception as e:
                log.error(f'Unhandled Update Exception {e}')
        else:
            log_subprocess_result(subprocess.call(
                ['sudo', 'git', 'clone', 'https://github.com/Jimbo145/SaabHeadUnit.git', '/usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit']))
        if await copy_files():
            subprocess.call(['sudo', 'systemctl', 'start', 'saab.service'])

if __name__ == "__main__":

    # jh = journal.JournalHandler()
    # jh.setLevel(logging.INFO)
    # log.addHandler(jh)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    log.addHandler(sh)
    log.setLevel(logging.INFO)

    subprocess.call(['xhost', '+', 'local:'])

    log.info("Saab Update Starting")
    asyncio.run(main())