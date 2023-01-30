import subprocess
import asyncio
import git #pip install GitPython 



async def main() -> None:

    """The main function that runs in the loop."""
    result = subprocess.run(['sudo', 'ip', 'link', 'set', 'can0', 'up', 'type', 'can', 'bitrate', '33300'])
    internet_connected = False
    while internet_connected == False:
        result = subprocess.run(['ping', '8.8.8.8', '-c', '1'])
        if(result.returncode == 0):
            internet_connected = True
        await asyncio.sleep(0.1)
    
        # Wait for next message from AsyncBufferedReader

    try:
        git.Repo.clone_from('https://github.com/Jimbo145/SaabHeadUnit.git','/home/pi/SaabHeadUnit')
    except:
        pass
    g = git.cmd.Git("/home/pi/SaabHeadUnit")
    g.pull('origin')

    subprocess.call(["python", "saabCan.py"])
        
        

        



try:
    if __name__ == "__main__":
        
        print("Starting...")
        asyncio.run(main())
except KeyboardInterrupt:
    print("Stopping...")