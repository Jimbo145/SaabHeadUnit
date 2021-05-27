#include <pigpio.h>
#include <iostream>
#include <string>
#include <thread>
#include <chrono> 
#include <mutex>


using namespace std;

void runSlave();
void closeSlave();
int getControlBits(int, bool);

std::mutex m;
char ScreenBuffer[9][106][8];

const int slaveAddress = 0x3C; // <-- Your address of choice
bsc_xfer_t xfer; // Struct to control data flow


template <typename I> std::string n2hexstr(I w, size_t hex_len = sizeof(I)<<1) {
    static const char* digits = "0123456789ABCDEF";
    std::string rc(hex_len,'0');
    for (size_t i=0, j=(hex_len-1)*4 ; i<hex_len; ++i,j-=4)
        rc[i] = digits[(w>>j) & 0x0f];
    return rc;
}


void printScreenBuffer(char (*buf)[106][8]){
    while(1){
        for(int x = 0; x < 8; x++){
            for(int y = 0; y < 8; y++){
                string output = "";
                for(int z = 0; z < 106; z++){
                    
                    if( ScreenBuffer[x][z][y] == 1){
                        output += "1";
                    }else{
                        output += "0";
                    }
                    
                
                }
                cout << output;
                cout << "\n\r";
            }
        }
        cout << "\n\r";
        cout << "\n\r";
        std::this_thread::sleep_for (std::chrono::seconds(10));
    }
    
    
}

void insertByte(char inputByte, char (*buf)[106][8], uint8_t page, uint8_t col){
    
    m.lock();
    buf[page][col][0] = (inputByte & 1<<7)>>7;
    buf[page][col][1] = (inputByte & 1<<6)>>6;
    buf[page][col][2] = (inputByte & 1<<5)>>5;
    buf[page][col][3] = (inputByte & 1<<4)>>4;
    buf[page][col][4] = (inputByte & 1<<3)>>3;
    buf[page][col][5] = (inputByte & 1<<2)>>2;
    buf[page][col][6] = (inputByte & 1<<1)>>1;
    buf[page][col][7] = (inputByte & 1<<0)>>0;
     m.unlock();
}
    

int main(){
    // Chose one of those two lines (comment the other out):
    thread th1(printScreenBuffer, ScreenBuffer);
    runSlave();

    //closeSlave();

    th1.join();

    return 0;
}

void runSlave() {
    gpioInitialise();
    cout << "Initialized GPIOs\n";
    // Close old device (if any)
    xfer.control = getControlBits(slaveAddress, false); // To avoid conflicts when restarting
    bscXfer(&xfer);
    // Set I2C slave Address to 0x0A
    xfer.control = getControlBits(slaveAddress, true);
    int status = bscXfer(&xfer); // Should now be visible in I2C-Scanners
    
    if (status >= 0)
    {
        cout << "Opened slave\n";
        xfer.rxCnt = 0;
        while(1){
            bscXfer(&xfer);
            if(xfer.rxCnt > 0) {
                uint8_t col = 0;
                uint8_t page = 0;
                bool updateBuffer = false;
                bool bufferAddressSeen = false;
                
                cout << " count " << xfer.rxCnt << "\n\r";
                string message = "";
                uint8_t skipMessage = 0;
                for(int i = 0; i < xfer.rxCnt; i++){
                    char d = xfer.rxBuf[i];
                    message += " " + n2hexstr(d);
                    if(updateBuffer && skipMessage == 7){
                        insertByte(d, ScreenBuffer, page, col);
                        col++;
                    }else if(bufferAddressSeen == true && d  == 0x40){
                        skipMessage++;
                    }else if(d  >= 0x40 and d <= 0x48){
                        page = d & 0b00111111;
                        bufferAddressSeen = true;
                    }
                }
                cout << " message " << message << "\n\r";                  
                    
            }
        }
    }else
        cout << "Failed to open slave!!!\n";
}

void closeSlave() {
    gpioInitialise();
    cout << "Initialized GPIOs\n";

    xfer.control = getControlBits(slaveAddress, false);
    bscXfer(&xfer);
    cout << "Closed slave.\n";

    gpioTerminate();
    cout << "Terminated GPIOs.\n";
}


int getControlBits(int address /* max 127 */, bool open) {
    /*
    Excerpt from http://abyz.me.uk/rpi/pigpio/cif.html#bscXfer regarding the control bits:

    22 21 20 19 18 17 16 15 14 13 12 11 10 09 08 07 06 05 04 03 02 01 00
    a  a  a  a  a  a  a  -  -  IT HC TF IR RE TE BK EC ES PL PH I2 SP EN

    Bits 0-13 are copied unchanged to the BSC CR register. See pages 163-165 of the Broadcom 
    peripherals document for full details. 

    aaaaaaa defines the I2C slave address (only relevant in I2C mode)
    IT  invert transmit status flags
    HC  enable host control
    TF  enable test FIFO
    IR  invert receive status flags
    RE  enable receive
    TE  enable transmit
    BK  abort operation and clear FIFOs
    EC  send control register as first I2C byte
    ES  send status register as first I2C byte
    PL  set SPI polarity high
    PH  set SPI phase high
    I2  enable I2C mode
    SP  enable SPI mode
    EN  enable BSC peripheral
    */

    // Flags like this: 0b/*IT:*/0/*HC:*/0/*TF:*/0/*IR:*/0/*RE:*/0/*TE:*/0/*BK:*/0/*EC:*/0/*ES:*/0/*PL:*/0/*PH:*/0/*I2:*/0/*SP:*/0/*EN:*/0;

    int flags;
    if(open)
        flags = /*RE:*/ (1 << 9) | /*TE:*/ (1 << 8) | /*I2:*/ (1 << 2) | /*EN:*/ (1 << 0);
    else // Close/Abort
        flags = /*BK:*/ (1 << 7) | /*I2:*/ (0 << 2) | /*EN:*/ (0 << 0);

    return (address << 16 /*= to the start of significant bits*/) | flags;
}