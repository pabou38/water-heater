import ssd1306
from machine import Pin
from time import sleep
import sys

# https://docs.micropython.org/en/latest/esp8266/quickref.html#ssd1306-driver

oled_w = None
oled_h = None

"""
print("ssd 1306 __name__", __name__) 
# when imported ssd 1306 __name__ my_ssd1306

try:
    print ("ssd 1306 argv",sys.argv) 
    # when imported ssd 1306 argv []
except:
    pass
"""

def create_ssd1306(oled_width, oled_height, i2c, reset=None):
# oled 60, 0x3c
    print("create ssd1306 oled")
    global oled_w
    global oled_h
    
    oled_w = oled_width
    oled_h = oled_height
    try:

        # https://github.com/orgs/micropython/discussions/10820
        # WARNING!!!!! built in oled S2 pico need reset GPIO 18

        if reset is not None:
            oled_reset = Pin(18, Pin.OUT, value=1)


        #https://randomnerdtutorials.com/micropython-oled-display-esp32-esp8266/
        oled = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c) # using 32 on 64 oled makes char bigger

        oled.contrast(255)  # bright
        oled.invert(0)      # display normal , ie write 1 to lit
        # oled.rotate(False)  # do not rotate 180 degrees 'SSD1306_I2C' object has no attribute 'rotate'
        #oled.poweron()    # does not seem to ne necessary
        
        # display version and errors counters from RTC memory
        oled.fill(0) # with black , 1 with white
        oled.text("ssd1306", 0, 0) # X,Y
        oled.text("init", 0, 10) # X,Y
        oled.show()
        return(oled)

        # 64 , ie 6,5 lines 
    
    except Exception as e:
        print('Exception cannot create oled ' , str(e))
        return(None)
    

#################
# RAZ screen and write several lines (passed as list)
# oled = None, no oled available (so that this can be used generically)
#################

def lines_oled(oled, l, space=10): # list of lines
    if oled is None:
        return(False)

    oled.fill(0)
    y=0 # top of screen vertical 
    x = 0 # far left horizontal

    try:

        for l1 in l:
            # color 1=white (default)
            # x where the text starts
            # y where the text is displayed vertically. next line y = 10
            oled.text(l1, x, y, 1) # last param is pixel, can be omitted y)
            y = y + space # one line in Y pixels vertical

        oled.show()
        return(True)
    
    except Exception as e:
        print("exception writing to oled %s" %str(e))
        return(False)

#################
# overwrite ONE line (passed as str)
# oled = None, no oled available
#### WARNING. just doing.text() does not work. write on TOP of previous bitmap, not replaces it
# to overwrite line, first write a rectangle
#################

def line_oled(oled, line_nb, s): # line number starts at 0
    if oled is None:
        return(False)
    
    H = 10 # number of pixels in heigth for one character with default font

    y = line_nb * H # one line in X pixels
    x = 0 # far left horizontal

    try:
        # raz bitmap first
        # display.fill_rect(10, 10, 107, 43, 1)   # draw a solid rectangle 10,10 to 117,53, colour=1


        """
        # WTF line is drawn correctly, but rect and fill_rect behaves as if 0,y, 127, y+2H

        oled.line(0, y, 127, y+H, 1) 
        oled.show()
        sleep(2)

        oled.rect(0, y, 127, y+H, 1) 
        oled.show()
        sleep(2)

        oled.fill_rect(0, y, 127, y+H, 1) 
        sleep(2)

        could be bug in driver. brutal force raz for now, making sure the rectangle is y, y+H; I may look at driver later
        """
        for i in range(H):
            for j in range(127):
                oled.pixel(j, y+i, 0)

        #oled.text("                ",x,y,1) does not work. add to existing bitmap, do not replace it
        
        oled.text(s,x,y,1) # last param is pixel, default 1, ie white on black background, can be omitted y)
        oled.show()
        return(True)
    
    except Exception as e:
        print("exception writing to oled %s" %str(e))
        return(False)


if __name__ == "__main__":
    
    print("oled running as main")

    W= 128
    H= 64
    i2c = None
    
    scl_gpio = 22
    sda_gpio = 14 

    import my_i2c
    port = 0
    print("create i2c")
    i2c = my_i2c.create_i2c(port, gpio_scl= scl_gpio, gpio_sda= sda_gpio)

    if i2c is None:
        print("no i2c devices detected. exit")
        sys.exit(1)
        
    else:
        print("i2c created AND device(s) detected")
        
        
    print("create oled")
    oled = create_ssd1306(W,H,i2c)

    if oled is not None:
        
        print("oled ok")

        # 64, ie 6,4 lines
        lines_oled(oled, ["hello", "esp", "testing", "oled", "4", "5"])
        sleep(2)
        
        for n in range(5):
            line_oled(oled, n, "line %d" %n)
            sleep(2)
            
    else:
        print("oled not available")
        
        
            
        
        
