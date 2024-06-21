#include <pigpio.h>
#include <iostream>
#include <string>
#include <thread>
#include <chrono> 
#include <mutex>

#include <SDL2/SDL.h>


using namespace std;

void runSlave();
void closeSlave();
int getControlBits(int, bool);

std::mutex m;

const uint PIXEL_SIZE = 4;
const uint PAGE_SIZE = 8;
const uint COLUMN_SIZE = 106;
const uint ROW_SIZE = 8;


const int slaveAddress = 0x3C; // <-- Your address of choice

bsc_xfer_t xfer; // Struct to control data flow
char ScreenBuffer[PAGE_SIZE][COLUMN_SIZE][ROW_SIZE];



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

void graphicScreenBuffer(char (*buf)[106][8]){
    
    if (SDL_Init(SDL_INIT_VIDEO) != 0){
        std::cout << "SDL_Init Error: " << SDL_GetError() << std::endl;
        //return 1;
        std::terminate();
    }

    SDL_Window *win = SDL_CreateWindow("", 100, 100, (COLUMN_SIZE * PIXEL_SIZE), (ROW_SIZE * PAGE_SIZE * PIXEL_SIZE), SDL_WINDOW_SHOWN);
    if (win == nullptr){
        std::cout << "SDL_CreateWindow Error: " << SDL_GetError() << std::endl;
        SDL_Quit();
        //return 1;
        std::terminate();
    }
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    if (ren == nullptr){
        SDL_DestroyWindow(win);
        std::cout << "SDL_CreateRenderer Error: " << SDL_GetError() << std::endl;
        SDL_Quit();
        //return 1;
        std::terminate();
    }

    
    SDL_Surface *surface = surface = SDL_CreateRGBSurface(0, (COLUMN_SIZE * PIXEL_SIZE), (ROW_SIZE * PAGE_SIZE * PIXEL_SIZE), 32, 0, 0, 0, 0);
    //Clear the Surface
    SDL_FillRect(surface, NULL, SDL_MapRGB(surface->format, 0, 0, 0)); 

    
    SDL_Texture *tex;
    while(true){
        
        for(int page = 0; page <= PAGE_SIZE; page++){
            for(int row = 0; row < ROW_SIZE; row++){
                for(int col = 0; col < COLUMN_SIZE; col++){
                    SDL_Rect pixeldrawRect;
                    pixeldrawRect.x = col * PIXEL_SIZE;
                    pixeldrawRect.y = (page * PAGE_SIZE * PIXEL_SIZE) + (row * PIXEL_SIZE);
                    pixeldrawRect.w = PIXEL_SIZE;
                    pixeldrawRect.h = PIXEL_SIZE;
                    if( ScreenBuffer[page][col][row] == 1){
                        SDL_FillRect(surface, &pixeldrawRect, SDL_MapRGB(surface->format, 0, 255, 0));
                    }else{
                        SDL_FillRect(surface, &pixeldrawRect, SDL_MapRGB(surface->format, 0, 0, 0));
                    }
                    
                
                }
            }
        }
        SDL_Rect pixeldrawRect;
        pixeldrawRect.x = 0;
        pixeldrawRect.y = 252;
        pixeldrawRect.w = PIXEL_SIZE;
        pixeldrawRect.h = PIXEL_SIZE;
        SDL_FillRect(surface, &pixeldrawRect, SDL_MapRGB(surface->format, 0, 0, 255));

        tex = SDL_CreateTextureFromSurface(ren, surface);
        
        if (tex == nullptr){
            SDL_DestroyRenderer(ren);
            SDL_DestroyWindow(win);
            std::cout << "SDL_CreateTextureFromSurface Error: " << SDL_GetError() << std::endl;
            SDL_Quit();
            //return 1;
            std::terminate();
        }

        //First clear the renderer
        SDL_RenderClear(ren);
        //Draw the texture
        SDL_RenderCopy(ren, tex, NULL, NULL);
        //Update the screen
        SDL_RenderPresent(ren);
        //Take a quick break after all that hard work
        std::this_thread::sleep_for (std::chrono::seconds(10));
    }
    SDL_FreeSurface(surface);

    SDL_DestroyTexture(tex);
    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
}
    
//#define TEXT_PRINTING

int main(){

    #ifdef TEXT_PRINTING
    thread th1(printScreenBuffer, ScreenBuffer);
    #endif
    thread thSDL(graphicScreenBuffer, ScreenBuffer);

    runSlave();


    //closeSlave();
    #ifdef TEXT_PRINTING
    th1.join();
    #endif

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
                    if(bufferAddressSeen && updateBuffer){
                        insertByte(d, ScreenBuffer, page, col);
                        col++;
                    }else if(bufferAddressSeen == true && d  == 0x40){
                        updateBuffer = true;
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