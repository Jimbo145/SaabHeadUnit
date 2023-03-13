import subprocess
import asyncio



async def main() -> None:

    """The main function that runs in the loop."""
    try:
        result = subprocess.run(['sudo', 'ip', 'link', 'set', 'can0', 'up', 'type', 'can', 'bitrate', '33300'])
    except:
        pass
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