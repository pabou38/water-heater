#https://phixed.co/blog/micropython-workflow/
#https://github.com/andrethemac/max17043.py 

# reset in case of  wifi error or i2c error or blynk error

##############################
# ecs v1: power sensors with GPIO H, ie provides vcc. one gpio per sensor (oled, dallas). seems lipo gauge always powered
# ecs v2: power sensors with GPIO L, ie provides gnd. compatible with mosfet , ie load between vcc and drain. gate H connects drain to source, ie gnd
#   ONE GPIO for all 3
#   battery NOT connected to lipo gauge jst, so lipo gauge not always powered
#   battery connected to ESP32 jst. lipo gauge vcc connected to vbat, gnd connected to GPIO

# measure ina219, 0,1ma resolution
#    deep sleep 0 to 0.1 ma
#    running , 30 - 50 ma peak 150 ma
#################################


app = "ecs v2"

version = "1.5 private server" # private server
version = "2.0 private server" # PCB and refactoring to use generic modules
version = "2.1 private server" # sensor processing move from (asynch) connect callback to inline in main
version = 2.2  # support one dallas only, support no oled, use mosfet gpio

from utime import ticks_ms
start_time=ticks_ms() # note t=time() is in seconds. to measure execution time

print('\n\n======== ECS ESP32 private server starting. %s ===========\n\n' %"%s %0.1f" %(app, version))

import gc
import os
import sys

from utime import sleep_ms, sleep, sleep_us, localtime, mktime
from machine import Pin, reset, WDT
from micropython import const

import _thread # run blynk as a tread


#import urandom # build in, in help('modules'), ie list of module that can be imported
# u means micropython ified. subset of Cpython
# correspond to micropython-random in pypi.org/projects/micropython-random
# note almost empty library. there to avoid import errors

#import uos # for random
#uos.random is also available uos.urandom(2) returns 2 bytes b'\xf4\xe8'


sensor_ok = const(1) # stored in RTC
sensor_failed = const(0)

sleep_sec_measure = 60*10 # deep sleep in sec between measure 
sleep_sec_error = 60 # deep sleep in sec if error
print("measure temperature every %d sec" %sleep_sec_measure)

repl = False # prevent watchdog to reset if running REPL (vs hang before entering deep sleep)


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

import secret # application agnostic, in my_modules
import my_sensors

##############
# logging
##############
import my_log

log = my_log.get_log(app, level = "debug")
log.info ("logger created")

######################
# GPIO
######################

# The ESP32 has two I2C channels and any pin can be set as SDA or SCL. default scl 22, sda 21
scl_gpio = 22

# bug in PCB. D21 ESP32 not connected. D2 on pin header for ESP8266 is connected to SDA, jumper from ESP32 D13 to ESP8266 D1
sda_gpio = 13
# problems if using D14. (H at boot?) invalid header when booting

sleep_gpio = 26 
# pull up. connect to gnd to disable going to deep sleep at the end of sensor processing
#  instead start repl and sleep forever , allows to flash in peace
print("connect GPIO %d to GND to disable deep sleep and start REPL as the end of sensor processing ... flash in peace)" %sleep_gpio)

ds18b20_gpio = 33 # multiple sensor possible, bus configuration
led_gpio = 5 # built in blue led  b.off() to lit

mosfet_gpio = 23 # gate. 

# put to gnd to power device
power_gpio = 25 # GND'   same pin for dallas, oled and fuel
# setting to Low will power sensors (already connected to Vcc)

# exit. force sys.exit 
exit_gpio = 27


######################
# Pin
######################

# Lolin D32 non Pro
led = Pin(led_gpio, Pin.OUT, value=0)
# to signal we are running. will be set to off just before going to deep sleep
print("led on: we are running")
led.off()

# sleep GPIO , input. prevent deep sleep and enter REPL at the end of processing if grounded
sleep_pin = Pin(sleep_gpio, Pin.IN, Pin.PULL_UP)
print("sleep pin (GND to NOT sleep) %d" %sleep_pin.value())

# to power ds18b20, fuel and oled from gpio
# set to 0 to power
power_pin = Pin(power_gpio, Pin.OUT, value=1)

# mosfet gate. external pulldown
# set to 1 to power
mosfet_pin = Pin(mosfet_gpio, Pin.OUT, value=0)

# exit GPIO , input. 
exit_pin = Pin(exit_gpio, Pin.IN, Pin.PULL_UP)


###############################
# list of Pin object, not gpio number
###############################

# will be set to low at deep sleep
pin_to_power_down = [mosfet_pin]

# configure (from output) to input mode with no pull resistor, ie floating to minimize consumption ?
pin_to_input = [power_pin, mosfet_pin]

# disable pull for input pins. assumes decreases consumption
pull_to_disable = [sleep_pin]


##############
# intro
##############
import deep_sleep
deep_sleep.print_reset_cause()
import intro

##############
# webrepl
##############
import my_webrepl


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
print("RTC: temp state, lipo state, temp error counter, lipo error counter, watchdog popped counter")

"""
0 temp error state
1 lipo error state

2 temp error count, incremented
3 lipo error count

4 watchdog popped counter
"""


################################
# power devices
# needed for oled
# power down just before going to deep sleep
# also part of deep sleep process, if defined 
################################
print("power sensors")
power_pin.off()
mosfet_pin.on()

sleep_ms(100)


################
# test temp now
################
print("testing temp")
# param is gpio nb, Pin created inside function
temp = my_sensors.read_dallas(ds18b20_gpio)
print(temp)


##############
# I2c
###############
import my_i2c
port = 0
i2c = my_i2c.create_i2c(port, gpio_scl= scl_gpio, gpio_sda= sda_gpio)

if i2c is None:
    print("no i2c devices detected. reset")
    sleep(10)
    reset() 
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
  """
  print("cannot create oled. reset")
  sleep(10)
  reset()
  """
  print("cannot create oled. keep going")
else:
  print("oled created")
  # 64, ie 6,4 lines
  # line 1 title
  # line 2 wifi, blynk, etc  status
  # line 3 and 4 temp sensor 
  # line 5 sleep status
  # line 6

  """
  print("testing oled")
  my_ssd1306.lines_oled(oled, ["line 1", "line 2", "line 3", "line 4", "line 5", "line 6", "line7"])
  sleep(5)

  for n in range(8):
    my_ssd1306.line_oled(oled, n, "over %d over" %n)
    sleep(2)

  sys.exit(1)
  """

my_ssd1306.lines_oled(oled, ["ecs v2", "meaudre", "robotics", "ts,ls,tc,lc,wc"])


#################################
# exit
#################################

if exit_pin.value() == 0:
   print("!!!!!!!! exit pin is LOW")
   (vcell, soc) = my_sensors.read_lipo_gauge(i2c)
   print(vcell, soc)
   temp = my_sensors.read_dallas(ds18b20_gpio)
   print(temp)
   sys.exit(1)



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
    my_ssd1306.line_oled(oled, 1, "wifi error. reset")
    
    del(wifi)
    sleep(d)
    reset()
else:
    print("wifi ok", ssid)
    # line 1 (start at 0), connection status
    my_ssd1306.line_oled(oled, 1, "wifi ok")


#######################
# blynk and wifi connection cleanup
########################

def disconnect(s):
    global stop_run

    print(s)
    logging.info(s)

    try:
        blynk_con.disconnect(err_msg=s)
    except:
        pass
    
    sleep(2) # time for blynk to run and process disconnect ??

    stop_run= True
    sleep(2) # time for blynk.run to exit ??

    try:
        wifi.disconnect()
    except:
        pass

def disconnect_and_reset(s):
    try: # make sure reset ALWAYS executed
        disconnect(s)
    except:
        pass

    sleep(5)
    reset()



def disconnect_and_deepsleep(s,sec):  # d in sec
    try:
        disconnect(s)
    except:
        pass

    # enter deep sleep
    go_to_deepsleep(sec)
  
    

#########################################################
# deep sleep ESP32
# param is sec
# includes pin to set before sleep. list of Pins , not GPIO
#########################################################

# enter deep sleep
def go_to_deepsleep(sec):

  print('ESP32 will deep sleep for %d sec. power down pins, turn led off' %sec)
  led.on() # turn build in led off

  #  pass pin list.
  # 
  deep_sleep.enter_deep_sleep(sec*1000, pull_to_disable=pull_to_disable, pin_to_down=pin_to_power_down, pin_to_input=pin_to_input)



#############################################
# watchdog a la main. prevent hang
# if already running repl , return
# else :
#   incremenent RTC error counter
#   write to blynk and oled
#   deep sleep
#############################################
def watchdog(sec): # tuple
  global repl
  print('\nwatchdog thread started to prevent hangs. sleep for %d sec' %sec)
  sleep(sec)
  print('\n!! watchdog thread still alive. running repl?: ', repl)

  # prevent deep sleep if in REPL
  if repl:
    print('watchdog: repl is true, do not deep sleep')
    return()

  # increment RTC error counter
  v = my_RTC.read_RTC(r,4)
  v = v + 1
  my_RTC.set_RTC(r,4, v)

  try:
    blynk_con.notify('ECS: watchdog popped') # not available for private server ?
  except:
    pass

  try:
    s = '%s: watchdog popped' %my_log.get_stamp() # use time stamp vs simple random number
    blynk_con.virtual_write(vpin_terminal, s)
    print(s)

    l = ["watchdog", "popped", "sleep"]
    my_ssd1306.lines_oled(oled,l)
  
    sleep(3) # blynk to complete before deep sleep ?

  except Exception as e:
    print('exception watchdog: ', str(e))
    l = ["watchdog", "exception", "sleep"]
    my_ssd1306.lines_oled(oled,l)

  finally:
    go_to_deepsleep(sleep_sec_error)  



#########################
# connect call back IN THE CONTEXT OF MAIN
# defined AFTER blynk_con creation
# NOT EXCECUTED WHEN USING MY_BLYNK_PRIVATE
# SO RATHER PROCESS SENSORS WHEN BLYNK IS CONNECTED
#########################

"""
@blynk_con.handle_event("connect")
def connect_handler():
  global first_connect
  
  print("   BLYNK: in connect call back")

  if first_connect: # avoid connect, disconnect
    print('   BLYNK: first connect')
    # do not send notif for each deep sleep
    try:
      blynk_con.notify('ECS starting')
      blynk_con.email('pboudalier@gmail.com', 'ecs', 'starting')
    except:
      pass

    first_connect = False
    process_sensors()

  else: # not first connect
    print("   BLYNK: not first connect")
    # do not read again
    return()

########### connect call back in main ###################


@blynk_con.handle_event("disconnect")
def disconnect_handler():
  print("   BLYNK: in disconnect call back")
"""


###########################################
# THIS IS WHERE ALL THE SENSORS PROCESSING IS DONE
# read temp sensors and publish to blynk
# set update_done gobal
# main wait on this variable, and will either sleep or run REPL
###########################################

def process_sensors():
  global update_done  # set to 1 (update performed) or -1. 
  global temp_haut, temp_milieu # set in connect call back, used in main
  global oled
  global r
  
  # we should only be in first connect call back
  ####################################
  # read all sensors
  ####################################

  print('process sensors')


  ############
  # lipo
  ############

  (vcell, soc) = my_sensors.read_lipo_gauge(i2c)
  print(vcell, soc)

  if vcell == None :
    s = 'error lipo sensor'
     
  else:
    s = 'cell %0.1f,soc %0.1f'  %(vcell, soc)
    
  print(s)

  #####################
  # fuel status on line 2
  #####################
  my_ssd1306.line_oled(oled,2,s)
    
  # also vbat from onboard ADC
  # vcell == None for error


  ############
  # temp
  ############

  temp = my_sensors.read_dallas(ds18b20_gpio)
  # temp == [] for error

  if temp != [] and len(temp) == 2:
    """
    how do I know which one is one ?
    looking at the data, should be as below
    """
    temp_haut = temp[1] 
    temp_milieu = temp[0]
    s = 'temp: haut %0.1f, milieu %0.1f'  %(temp_haut, temp_milieu)

  elif temp == []:
    s = 'error temp sensor. NO sensors at all'

  else: 
    # debug. only one sensor connected
    temp_haut = temp[0] 
    temp_milieu = temp[0]
    s = 'ONE: haut %0.1f, milieu %0.1f'  %(temp_haut, temp_milieu)
     

  print(s)

  #####################
  # temp status on line 3
  #####################
  my_ssd1306.line_oled(oled,3,s)


  ########################################################
  # publish to blynk
  # update RTC state and error count
  # write to oled
  # NOTE: with private server, notify and email would not work ??
  ########################################################
  
  print('sensor read, publishing ..')

  if (blynk_con.is_server_alive()) == True:

    # send notification and email for sensor first fail, or first recovered only, based on status stored in RTC memory
    # ie avoid flooding

    #########################
    # update Blynk
    # update RTC (state and error counters)
    # send notification and email ONLY when state change
    ##########################


    ############
    # lipo
    # error is vcell == None
    ############

    if vcell != None: # sensor OK

      ##### LIPO OK

      # VPIN
      blynk_con.virtual_write(vpin_vsoc, int(soc))
      blynk_con.virtual_write(vpin_vbat, vbat)

      s = "%s soc %d vbat %0.1f" %(my_log.get_stamp(),soc,vbat)
      blynk_con.virtual_write(vpin_terminal, s)

      ###############
      # RTC
      ###############
      if r.memory()[1] == sensor_failed: # we were in a sensor error state.
        # STATE CHANGE frpm NOK to OK
        print('send notification: lipo recovered')
        try:
          blynk_con.notify('ECS: lipo sensor recovered: %s ' %(str(vcell)))
          blynk_con.email('pboudalier@gmail.com', 'ecs micropython lipo sensor recovered')
        except:
          pass

        # reset error condition in RTC memory. NOK to OK
        my_RTC.set_RTC(r,1, sensor_ok)
        print ('lipo error status reset to OK. RTC: ', r.memory())

      else:
        pass # status is OK and sensor read is OK
        # no state change OK to OK

    else: 
      ##### LIPO NOK
      
      # increment lipo RTC error counter
      print("about to increment lipo error counter", r.memory())
      v = my_RTC.read_RTC(r,3)
      v = v + 1
      my_RTC.set_RTC(r,3, v)
      print("incremented lipo error counter", r.memory())

      # write error to blynk terminal at each failed read
      # write content of RTC error counters
      s = '%s: lipo sensor error' %my_log.get_stamp() # use time stamp vs simple random number
      print(s)
      blynk_con.virtual_write(vpin_terminal, s)
      s = 'RTC counters: %s'%(str(r.memory()))
      print(s)
      blynk_con.virtual_write(vpin_terminal, s)  # b'\x01
      

      # update RTC state
      if r.memory()[1] == sensor_ok: # we were in a sensor ok state.
        # STATE CHANGE from OK to NOK
        print('lipo was in OK state. now in error. send notification: failed')

        # send notif in state change only
        try:
          blynk_con.notify('ECS: lipo sensor failed !! ')
          blynk_con.email('pboudalier@gmail.com', 'ecs micropython: lipo sensor failed')
        except:
          pass

        # set lipo status to error
        my_RTC.set_RTC(r,1, sensor_failed)
        print ('lipo status set to error. RTC: ', r.memory())

      else:

        print('lipo state was error and still is')
        # no state change NOK to NOK

    ############
    # temp
    # only ONE temp sensor OK is considered error
    ############

    if temp != [] and len(temp) == 2: # ALL temp sensor OK

      ##### temp OK

      # Blynk VPIN
      blynk_con.virtual_write(vpin_haut, temp_haut) # temp top, v43, red
      blynk_con.virtual_write(vpin_milieu, temp_milieu) # temp mid, v44, orange

      # Blynk terminal, incl get time stamp(TZ) and flags
      s = "%s temp_haut %0.1f temp_milieu %0.1f" %(my_log.get_stamp(),temp_haut,temp_milieu)
      blynk_con.virtual_write(vpin_terminal, s)

      # Blynk terminal write RTC flag as well
      s1=r.memory() #  will print b'\x01\x01\x00\x00\x00'
      s1 = '%s %s %s %s %s' %(s1[0], s1[1], s1[2], s1[3], s1[4]) # str to print
      blynk_con.virtual_write(vpin_terminal, s1)

      ###############
      # RTC
      # state and counters
      ###############

      if r.memory()[0] == sensor_failed: # we were in a sensor error state.
        # state change from NOK to OK

        #print('send notification: recovered')
        #blynk.notify('ECS: temp sensor recovered: %0.1f %0.1f ' %(temp_haut, temp_milieu))
        #blynk.email('pboudalier@gmail.com', 'ecs micropython temp sensor revovered')
        # reset error condition in RTC memory
        
        my_RTC.set_RTC(r,0,sensor_ok)

        print ('temp error status set to OK. RTC:', r.memory()) 
      else:
        pass # status is OK and sensor read is OK
        # no state change OK to OK

    else: # temp sensor failed. at least one
      ##### temp NOK

      """
      would distort the graph
      blynk.virtual_write(vpin_haut, 100) # temp top, v43, red
      blynk.virtual_write(vpin_milieu, 100) # temp mid, v44, orange
      """

      # RTC
      # increment RTC error counter
      print("about to increment temp error counter", r.memory())
      v = my_RTC.read_RTC(r,2)
      v = v + 1
      my_RTC.set_RTC(r,2, v)
      print("incremented temp error counter", r.memory())

      # VPIN
      # write error to blynk terminal at each failed read
      s = ('%s: temp sensor error' %my_log.get_stamp()) # use time stamp vs simple random number
      print(s) # error message
      blynk_con.virtual_write(vpin_terminal, s)

      s = 'flags: %s'%(str(r.memory()))
      print(s)
      blynk_con.virtual_write(vpin_terminal, s)  # b'\x01


      if r.memory()[0] == sensor_ok: # we were in a sensor ok state.
        print('send notification: failed')
        try:
          blynk_con.notify('ECS: temp sensor failed !! ')
          blynk_con.email('pboudalier@gmail.com', 'ecs micropython temp sensor failed')
        except:
          pass

        # set error condition in RTC memory
        my_RTC.set_RTC(r,0, sensor_failed)

        print ('temp error status set to failed in RTC: ', r.memory())
      else:
        print('temp sensor still failing')


    print("RTC memory updated: ",r.memory()) # b'\x01\x00\x00\x01\x00'

    ##################
    # RTC to oled last line
    #################

    s1=r.memory() #  will print b'\x01\x01\x00\x00\x00'
    s1 = '%s %s %s %s %s' %(s1[0], s1[1], s1[2], s1[3], s1[4]) # str to print

    #  str(r.memory()), ie  b'\x01\x00\x00\x01\x00' as a str is too wide
  
    my_ssd1306.line_oled(oled,5,s1)

    update_done = 1 # to signal ok to main thread. main waiting on this global var
    # could have had sensor error

  else: # server not alive

    print('   BLYNK: blynk server not alive, could not update')

    l = ["blynk", "not alive"]
    my_ssd1306.lines_oled(oled,l)
    # maybe oled worked
    update_done = -1 # to signal blynk error to main thread. 

  print('end processing')

# end processing sensor update_done = 1 (sensor ok or nok) or -1 if blynk error
################################################################################
    



###########################################
############################
# main processing loop
############################
############################################


first_connect = True

update_done = 0 
# global. set to 1 or -1 after sensor processing.

temp_haut = 0.0
temp_milieu = 0.0


# prevent "hang"
print('start watchdog thread')
# this thread should "die" when ESP goes to deep sleep. if still there, this is a problem
_thread.start_new_thread(watchdog, (60,))  # param need to be a tuple

##########################
# Blynk  private
# defined before call back(otherwize blynk_con not defined)
##########################

import vpin # application specific, in app directory
import my_blynk_private

# blynk virtual pin
vpin_haut = vpin.vpin_haut
vpin_milieu = vpin.vpin_vsoc
vpin_vsoc = vpin.vpin_vsoc
vpin_terminal = vpin.vpin_terminal
vpin_vbat = vpin.vpin_vbat

blynk_token = secret.blynk_token_ecs

# cannot use log=None. create object with or without log defined is done in my_blynk
# log is blynk library internal log
# library retrieves blynk server from wifi ssid
blynk_con = my_blynk_private.create_blynk(blynk_token, wifi=wifi, log=True)



###########################
#### start blynk.run thread
###########################
_thread.start_new_thread(my_blynk_private.run_blynk, (blynk_con,))


###########################
#### connect to Blynk server
###########################


print("connect to blynk")
ret = my_blynk_private.connect_blynk(blynk_con)
print("connect returned %s" %ret)

print("wait for blynk to connect")
ret= my_blynk_private.wait_blynk(blynk_con)
if ret == False:
    s = "cannot connect to blynk"
    print(s)
    my_ssd1306.lines_oled(oled,["blynk error", "reset"])
    sleep(3)
    disconnect_and_reset(s)

else:
  print("!!! Blynk connected. create micropython watchdog")
  my_ssd1306.line_oled(oled,1,"blynk OK")

  # process synchronously in main (vs in connect call back)

  w_sec = 90
  print("create watchdog %d sec" %w_sec)
  wdt = WDT(timeout=w_sec*1000)
  # if wdt not fed, will reset
  wdt.feed()


  ######################
  # process sensors
  ######################

  process_sensors()


"""
not needed anymore , as 
print('\nwait for update_done from Blynk connect call back') # wait for sensor value update into blynk server
while update_done == 0: # will be set to 1 or -1 for blynk error
  sleep(1)
  #print('update done ? ', update_done)
  #print('E', end='')
"""


print('sensor updated, update_done: %d (1:OK, -1:error)' %update_done)

if update_done == 1: # OK
  l = ["sensor", "OK"]

  my_ssd1306.line_oled(oled,1,"sensor ok")

if update_done == -1: # blynk error
    l = ["sensor", "ERROR"]
    my_ssd1306.line_oled(oled,1,"sensor error")

  
# read test pin (pull up)
# connect GPIO 15 to gnd to avoid any deep sleep. allow to reflash in peace
if sleep_pin.value() == 0:
  print('==== > sleep pin is pulled LOW. no deep sleep, start repl and idle forever')
  my_ssd1306.line_oled(oled, 4, "START REPL")
  
  my_webrepl.start_webrepl()
  
  repl = True
  print('sleep forever while in repl, until keyboardInterrupt. repl: %s' %repl)

  my_webrepl.in_repl(wdt)
  # sleep and eventually sys.exit

else:
  my_ssd1306.line_oled(oled, 4, "DEEP SLEEP")
  sleep(5)

  print('==== > sleep pin is HIGH. deep sleep')

  ############################
  # power down sensors
  # also done as part of deep sleep anyway
  ############################
  print("power down sensors")
  power_pin.value(1)
  mosfet_pin.value(0)

  print ('script execution time(ms): ', ticks_ms()-start_time)

  s= 'disconnect and deep sleep until next measure %d sec'% sleep_sec_measure
  print(s)

  ################
  # enter deep sleep
  ################
  disconnect_and_deepsleep(s, sleep_sec_measure)




