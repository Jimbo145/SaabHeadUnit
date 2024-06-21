import time
import sys
import threading 
import pigpio
import websocket
import json
from gpiozero import CPUTemperature
try:
    import thread
except ImportError:
    import _thread as thread
import can
from can.interface import Bus
from smbus2 import SMBus
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import Qt
from collections import deque



def PrintDisplay():
    for x in range(8): #page
        for y in range(8): #row
            line = str(x) + "," + str(y) + ": " 
            for z in range(110):
                #For every page display each row incrementally for each column
                line += str(displayFull[x][z][y])
            print(line, flush=True)

displayFull = []
def InitDisplay():
    for x in range(8): #page
        displayFull.append([])
        for z in range(110): #col
            displayFull[x].append([0,0,0,0,0,0,0,0])
                

        
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.label = QtWidgets.QLabel()
        canvas = QtGui.QPixmap(106, 65)
        self.label.setPixmap(canvas)
        self.setCentralWidget(self.label)
        self.draw_something()

    def draw_something(self):
        painter = QtGui.QPainter(self.label.pixmap())
        painter.drawLine(10, 10, 300, 200)
        painter.end()

cpu = CPUTemperature(min_temp=50, max_temp=90)
pio = pigpio.pi()


# Python-Can.readthedocs.io
can.rc['interface'] = 'socketcan'
can.rc['channel'] = 'can0'
can.rc['bitrate'] = 500000

COLUMN_START_ADR_MASK = 0b00001111

column_start_adr = 0


I2C_ADDR = 0x3C
def i2c(id, tick):
    global pio

    s, b, data = pio.bsc_i2c(I2C_ADDR)

    if s < 0:
        print("i2c error " + str(s))

    #if b:
    x = ""
    saveData = False
    index = 0
    step = 10
    pageIndex = 0
    for d in data:
        x = x + str(hex(d)) + " "
        if saveData == True:
            print(str(pageIndex) + "," + str(index))
            #displayFull[pageIndex][index] = byte_to_list(d)
            index = index + 1
        elif (d >= 0x40 and d <= 0x48):
            pageIndex = d  & 0b00111111
            saveData = True
            
        
    print(x, flush=True)
    if(saveData):
        #PrintDisplay()  

        print("\n\r", flush=True)  
       

i2cBuffer = deque([])
def i2c_quick_handle(id, tick):
    global pio

    s, b, data = pio.bsc_i2c(I2C_ADDR)
    
    if b:
        i2cBuffer.append([])
        for d in data:
            i2cBuffer[len(i2cBuffer)-1].append(d)   
       


def temp_monitor():
    temp = cpu.temperature
    while True:
        print('Temperature: {}C'.format(cpu.temperature))

        if temp > 65:
            pio.write(13, 1)

            # Stop the fan if the fan is running and the temperature has dropped
            # to 10 degrees below the limit.
        elif temp < 55:
            pio.write(13, 0)

        time.sleep(10)

def byte_to_list(num):
    lst = [0,0,0,0,0,0,0,0]
    lst[0] = (num & 1<<7)>>7
    lst[1] = (num & 1<<6)>>6
    lst[2] = (num & 1<<5)>>5
    lst[3] = (num & 1<<4)>>4
    lst[4] = (num & 1<<3)>>3
    lst[5] = (num & 1<<2)>>2
    lst[6] = (num & 1<<1)>>1
    lst[7] = (num & 1<<0)>>0
    return lst


def ws_state():
        while True:
            ws = websocket.WebSocket()
            ws.connect("ws://127.0.0.1:54545/state")
            ws.send(json.dumps(["volume"]))
            print(ws.recv())
            ws.close()
            time.sleep(10)

def volume_change(step_size):
    
    ws = websocket.WebSocket()
    ws.connect("ws://127.0.0.1:54545/action")
    if step_size > 0:
        ws.send(json.dumps({"increase_volume": step_size}))
    elif step_size < 0:
        ws.send(json.dumps({"decrease_volume": abs(step_size)}))
    ws.close()

def brightness_change(step_size):
    
    ws = websocket.WebSocket()
    ws.connect("ws://127.0.0.1:54545/action")
    if step_size > 0:
        ws.send(json.dumps({"increase_brightness ": step_size}))
    elif step_size < 0:
        ws.send(json.dumps({"decrease_brightness ": abs(step_size)}))
    ws.close()

def can_read():
    bus = can.interface.Bus('can0', bustype='socketcan')
    while True:
        message = bus.recv()
        print(message)    

def i2c_read():
    bus = SMBus(0)

def print_i2c_buf():
    while True:
        if len(i2cBuffer) > 0:
            messge = i2cBuffer.popleft()

            x = ""
            saveData = False
            index = 0
            step = 10
            pageIndex = 0
            for d in messge:
                x = x + str(hex(d)) + " "
                if saveData == True:
                    #print(str(pageIndex) + "," + str(index))
                    displayFull[pageIndex][index] = byte_to_list(d)
                    index = index + 1
                elif (d >= 0x40 and d <= 0x48):
                    pageIndex = d  & 0b00111111
                    saveData = True
                    
                
            print(x, flush=True)
            if(saveData):
                PrintDisplay()  

                print("\n\r", flush=True)  

        
def main():
    print("Starting Hardware")

    InitDisplay()

    pio.set_mode(13, pigpio.OUTPUT)

    t1 = threading.Thread(target=temp_monitor)  
    t1.daemon =  True
    #t1.start()

    t2 = threading.Thread(target=ws_state)  
    t2.daemon =  True
    #t2.start()

    t3 = threading.Thread(target=can_read)
    t3.daemon = True
    #t3.start()

    t4 = threading.Thread(target=print_i2c_buf)
    t4.daemon = True
    t4.start()

    

    
    try: 
        print("X Display")
        #app = QtWidgets.QApplication(sys.argv)
        #window = MainWindow()
        #window.show()
        #app.exec_()
    except:
        print("No X Display")
    

    e = pio.event_callback(pigpio.EVENT_BSC, i2c_quick_handle)

    pio.bsc_i2c(I2C_ADDR) # Configure BSC as I2C slave

    t4 = threading.Thread(target=i2c_read)
    t4.daemon = True
    #t4.start()


    while True:
        time.sleep(500)

    e.cancel()

    pio.bsc_i2c(0) # Disable BSC peripheral

    pio.stop()


if __name__ == "__main__":
    main()
    