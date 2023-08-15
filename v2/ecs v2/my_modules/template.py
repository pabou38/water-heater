
##################################################
# micropython template
###################################################


version = 1.51 #

import sys

from utime import sleep, localtime
#from utime import sleep_ms,  sleep_us, gmtime, mktime

from machine import Pin, reset, Timer
#from machine import RTC, I2C, ADC,  DEEPSLEEP, deepsleep, reset_cause, DEEPSLEEP_RESET, PWRON_RESET, HARD_RESET  
import _thread


###############################
# order
#  import
#  secret
#  logging
#  GPIO and Pins
#  pin to disable
#  intro, deep sleep
#  i2c, oled
#  wifi
#  webrepl
#  ping
#  ADC, RTC
#  Blynk


##############
# import
##############

# add with append or insert 
# name of dir in ESP32 file system
# this name exists on Windows file system (in micropython project directory)
# and is symlinked to HOME/Blynk/Blynk_client and HOME/micropython/"my modules" in Windows file system
# those dir are expected to be downloaded  (eg pymakr sync project) to ESP32 to /
# ESP32 file system
sys.path.append("/my_modules")
sys.path.insert(1,"/Blynk")
print("updated import path: ", sys.path)

# order: GPIO => i2c => OLED => WIFI => Blynk

##########
# secret
##########
import secret # application agnostic, in my_modules

##############
# logging
##############

import logging 
# from micropython-lib-master  a single logging.py vs logging dir
# https://github.com/micropython/micropython-lib/tree/master/python-stdlib/logging/examples

print('create logger, will display on stdout')
logging.basicConfig(level=logging.DEBUG)

logging.info("watering starting") 
# INFO:root:remote PZEM starting

# seems using logging.  creates problem inside function
log = logging.getLogger("watering")
log.info("starting")
# INFO:pzem:starting


##############
# logging
##############
app = "test"
version = 1.0
app_name = "%s v%0.1f" %(app, version)

import my_log
log = my_log.get_log(app_name, level = "debug")
log.info("%s starting" %app_name)


###########
# GPIO and Pins
###########
from machine import Pin
#led = Pin(led_gpio, Pin.OUT, value=0)
#led.off()
#sleep_pin = Pin(sleep_gpio, Pin.IN, Pin.PULL_UP)

###############################
# list of Pin object, not gpio number
###############################

# will be set to low at deep sleep
pin_to_power_down = []

# configure (from output) to input mode with no pull resistor, ie floating to minimize consumption ?
pin_to_input = []

# assumes decreases consumption, for Input pins
pull_to_disable = []


############
# intro
###########
import intro


##############
# deep sleep and disconnect
##############
import deep_sleep
deep_sleep.print_reset_cause()

print("stop run" , deep_sleep.stop_run)

##############
# I2c
###############
import my_i2c
port = 0
i2c = my_i2c.create_i2c(port, gpio_scl= scl_gpio, gpio_sda= sda_gpio)

if i2c is None:
    d = 20 # time to interrupt
    print("no i2c devices detected. reset in %d sec" %d)
    sleep(d)
    reset() # better to reset than exit 
else:
    print("i2c created AND device(s) detected")

################
# OLED
################
import my_ssd1306
W= 128
H= 64
oled = my_ssd1306.create_ssd1306(W,H,i2c)
sleep(1)

if oled is None:
  print("cannot create oled. reset")
  sleep(10)
  deep_sleep.my_reset(sleep_pin)
else:
  print("oled created")
  # 64, ie 6,4 lines
my_ssd1306.lines_oled(oled, ["ecs v2", "meaudre", "robotics"])

            
#############
# wifi
#############

own_ip="192.168.1.3" # static
own_ip=None  # dhcp

import my_wifi

print('start wifi')
wifi, ssid = my_wifi.start_wifi(own_ip=own_ip)
if wifi == None:
    d = 30
    print('cannot start wifi. reset in a %d sec' %d)
    
    del(wifi)
    sleep(d)
    reset()
else:
    print("wifi ok", ssid)

##############
# webrepl
##############
import my_webrepl

#################
# ping
#################
import my_ping

ret = my_ping.ping_ip("192.168.1.1")
s = "ping box returned %s" %ret
print(s)
logging.info(s)

#################
# ping thread
# thread to reset if ping fails
#################
import my_ping

print("start ping thread")
_thread.start_new_thread(my_ping.ping_thread, ("192.168.1.1", 30, logging, wifi))

############
# ADC
#############
import my_adc_esp32
vbat = my_adc_esp32.esp32_adc()
print('read vbat with adc: %0.2f' %vbat)

############
# RTC
############
import my_RTC
r = my_RTC.init_RTC([1,1,0,0,0])

##########################
# Blynk private
##########################

import vpin # application specific, in app directory
import my_blynk_private
from machine import WDT

# 8089 13809
# 9444 13810  use for app
# 7443 13811  admin

blynk_token = secret.blynk_token_ecs

# cannot use log=None. create object with or without log defined is done in my_blynk
# log is blynk library internal log
# library retrieves blynk server from wifi ssid

#### create blynk object
blynk_con = my_blynk_private.create_blynk(blynk_token, wifi=wifi, log=True)

#### start blynk.run thread
_thread.start_new_thread(my_blynk_private.run_blynk, (blynk_con,))
#####################
# case 2: blynk.run in main
# only case would be ESP8266, no thread module ??
# use timers to process sensor
# nothing else in main
#my_blynk_private.run_blynk(blynk_con, log = log)
#####################


#### connect to blynk server
print("connect to blynk")
ret = my_blynk_private.connect_blynk(blynk_con)
print("connect returned %s" %ret)

print("wait for blynk to connect")
ret= my_blynk_private.wait_blynk(blynk_con)
if ret == False:
    s = "cannot connect to blynk"
    print(s)
    logging.error(s)
    deep_sleep.disconnect_and_reset(s, wifi, blynk_con)  # this a operational error (ie could append in operation. for cabling errors (i2c, oled), use my_reset
else:
  print("!!! Blynk connected. create micropython watchdog")

  # process synchronously in main (vs in connect call back)

  w_sec = 90
  print("create watchdog %d sec. feed in main loop or else will reset" %w_sec)
  wdt = WDT(timeout=w_sec*1000)
  # if wdt not fed, will reset
  wdt.feed()


##### WARNING: do not sync yet. does not seem to work. wait after call back definition

###############
# widget call backs
# defined in my_blynk module, or in main
# control, display non push, display push
##############

#############
# control widget
#############
s = "write V%d" %0
@blynk_con.handle_event(s)
def f1(pin, value):
    global button_valve # 

    print("BLYNK: call back control widget", pin, value)
    button_valve = int(value[0])

#############
# REPL
#############
s = "write V%d" %0
@blynk_con.handle_event(s)
def f5(pin, value):
    global button_repl
    global repl_started

    print("BLYNK: call back control widget", pin, value)
    button_repl = int(value[0])

    if button_repl:
        # start webrepl 

        if repl_started: 
            pass
        else:

            repl_started = True
        
            ret = my_webrepl.start_webrepl(logging) # 

    else:
        # do nothing 
        pass


#############
# reset
#############
s = "write V%d" %0
@blynk_con.handle_event(s)
def f6(pin, value):
    global button_reset
    global stop_run
    print("BLYNK: call back control widget", pin, value)
    button_reset = int(value[0])

    if button_reset:
        disconnect_and_reset(s, wifi, blynl_con)



""""
### display widget
# FOR NON PUSH display widget
# will be called based on timer, set in widget itself
@blynk_con.handle_event('read V' + str(display_vpin))
def read_virtual_pin_handler(pin):
    i = random.randint(0, 255)
    print("BLYNK: call back non push display widget %d. rand %d" %(pin,i))
    blynk_con.virtual_write(pin, i)
"""


##################
# synching
# DO AFTER CALL BACK DEFINITION ????
# give time to virtual_sync call back to happen, 
# sync, ie data needed for processing
# do as early as possible ?, to give time to call back to run, before going in loop (which need the value)
# order ?
# otherwize could enter deep sleep with default value and not widget values
# or test ALL call backs happened
##################

to_sync = []
nb_to_sync = len(to_sync)
nb_sync = 0 # global, incremented in virtual_sync call backs

for x in to_sync:
    blynk_con.virtual_sync(x) 

######################################################
# wait for call back for specific widged (eg sleep button)
# could be done here or in main loop. choose what is best
######################################################
print("wait for sleep button to synch")
i = 0
while sleep_has_synced == False:
    sleep(1)
    i = i + 1
    if i>3:
        #blynk_con.virtual_sync(vpin_sleep) # ceinture et bretelles
        pass 

    if i > 20:
        
        disconnect_and_reset(s, wifi, blynk_con)

######################################################
# ADDITIONALLY, wait for call backs for other widgets needed in case of deep sleep
######################################################
for i in range(30):
    print("sync'ed: %d out of %d" %(nb_sync, nb_to_sync))
    if nb_to_sync == nb_sync:
        break
    sleep(1) # not a good idea for battery powered and deep sleep .. but well ..



#########################
# main processing LOOP
#########################

# _thread.start_new_thread(watch, (30,)) # 30 sec

def process():
    pass

while True:

    try:
        wdt.feed()
        process()

    except KeyboardInterrupt:
        s= "%s: got KeyboardInterrupt. disconnect and reset" %my_log.get_stamp()
        #disconnect_and_reset(s, wifi, blynk_con)
        sys.exit(1)
        

    except Exception as e:
        s = "%s: exception non keyboard interrupt %s. disconnect and reset" %(my_log.get_stamp(), str(e))
        disconnect_and_reset(s, wifi, blynk_con)
