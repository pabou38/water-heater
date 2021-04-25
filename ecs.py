#https://phixed.co/blog/micropython-workflow/
#https://github.com/andrethemac/max17043.py 

version = "1.3"

from utime import ticks_ms
start_time=ticks_ms() # note t=time() is in seconds. to measure execution time

print('\n\n================== ECS ESP32 boot starting. version %s =======================\n\n' %version)

import gc
import os
import sys

from machine import deepsleep, idle, reset_cause, DEEPSLEEP_RESET, DEEPSLEEP
from utime import sleep_ms, sleep, sleep_us, localtime, mktime
from machine import Pin, RTC, I2C, ADC
from micropython import mem_info, const, stack_use

import _thread # run blynk as a tread
import blynklib_mp as blynklib# no .mpy
import ntptime
import ssd1306

import urandom # build in, in help('modules'), ie list of module that can be imported
# u means micropython ified. subset of Cpython
# correspond to micropython-random in pypi.org/projects/micropython-random
# note almost empty library. there to avoid import errors

#import uos # for random
# uos.random is also available uos.urandom(2) returns 2 bytes b'\xf4\xe8'

from pb_max17043 import max17043

sensor_ok = const(1) # stored in RTC
sensor_failed = const(0)

################################ 
#https://randomnerdtutorials.com/esp32-pinout-reference-gpios/
#################################

sleep_sec_measure = 60*10 # deep sleep in sec between measure 
sleep_sec_error = 60 # deep sleep in sec if error

repl = False

# pin definition
test_gpio = 15 # connect to gnd to disable deep slep
ds18b20_gpio = 18 # multiple sensor possible, bus configuration
led_gpio = 5 # built in blue led  b.off() to lit

mosfet_gpio = 19 # gate
dallas_power_gpio = 16 # power vcc
oled_power_gpio = 17 # power vcc

# The ESP32 has two I2C channels and any pin can be set as SDA or SCL
scl = 22
sda = 21

# blynk virtual pin
vpin_haut = 43
vpin_milieu = 44
vpin_vsoc = 45
vpin_terminal = 46


# Lolin D32 non Pro
led = Pin(led_gpio, Pin.OUT, value=0)
# to signal we are running. will be set to off just before going to deep sleep
led.off()

# test GPIO , input. prevent deep sleep if grounded
test_pin = Pin(test_gpio, Pin.IN, Pin.PULL_UP)

# mosfet gate
mosfet_pin = Pin(mosfet_gpio, Pin.OUT, value=0)
mosfet_pin.on()

# to power ds18b20 from gpio
dallas_power_pin = Pin(dallas_power_gpio, Pin.OUT, value=0)

# to power oled from gpio
oled_power_pin = Pin(oled_power_gpio, Pin.OUT, value=0)

# will be set to low at deep sleep
pin_to_power_down = [oled_power_pin, dallas_power_pin, mosfet_pin]

#rand = urandom.randint(1,100)

# vbat 100K divisor. default input for ADC is 0 to 1V. use attenuation to extend input range 
# O to 4095
adc = ADC(Pin(35))
adc.atten(ADC.ATTN_11DB)    # set 11dB input attenuation (voltage range roughly 0.0v - 3.6v)
#ADC.ATTN_6DB: 6dB attenuation, gives a maximum input voltage of approximately 2.00v
adc_read = adc.read()
vbat = round((2*adc_read/4096) * 3.3, 2)
print('adc: %d , vbat: %0.2f' %(adc_read, vbat))


# check if the device woke from a deep sleep
if reset_cause() == DEEPSLEEP_RESET:
    print('ESP32: woke from a deep sleep')
else:
  print('ESP32: fresh boot')



####################################
#  RTC
####################################

def init_RTC(init):
  global r
  # pass list of bytes eg  [1, 1, 0, 0, 0]

  ###########################################
  # RTC 16KB of SRAM
  ###########################################

  # index into RTC memory, 2 bytes
  # r.memory()[0] is temp error state
  # r.memory()[1] is lipo error state
  # 2 number of temp read error since last reboot
  # 3 same for lipo
  # 4 number of watchdog popped

  r = RTC()
  mem = r.memory()  # content survives deep sleep
  print('RTC memory: ', mem)

  if (mem == b''):
    print('RTC memory empty. initializing..')
    #r.memory(bytearray(0b00000000)) # need object with buffer protocol

    # store x bytes in RTC  
    # layout
    # 1 , 1 : reset error condition for sensor error. send alarm only first error and recovered
    # 0, 0, 0 : number of temp error, lipo error, watchdog reset , SINCE LAST POWER UP

    r.memory(bytes(init)) # need object with buffer protocol
    mem = r.memory() # type bytes, immutable
    print('RTC memory: ', mem) #  b'\x01\x01\x00\x00\x00'

  # to test a value  r.memory() [i]

  # to set a value 
  # x=r.memory()
  # x=bytearray(x) make mutable
  # x[i]=1
  # r.memory(x)

  # bit operation possible as well
  # r.memory and wifi_error == 0 , test if bit not set
  # r.memory (r.memory() or wifi_error), set bit
  # r.memory (r.memory() and not wifi_error) reset bit

  else:
    pass
  
# return RTC at index i
def read_RTC(i):
  global r
  return(r.memory() [i])

# set RTC at index i with value
def set_RTC(i, value):
  global r
  x=r.memory()
  x=bytearray(x) #make mutable
  x[i]=value
  r.memory(x)

"""
import upip
#upip.install('picoweb')
#upip.install('utemplate')
upip.install('micropython-logging')
"""

print('content of /: ', os.listdir())
try:
  print('content of /lib: ', os.listdir('/lib'))
except Exception as e:
  print('content of /lib ', str(e))



##################################################
# repl
##################################################
def start_repl():
  # need to import once webrepl_setup from a usb/ttl connection to set password
  # creates webrepl_cfg.py (not visible in uPyCraft, visible w: os.listdir()
  # cannot just browse to IP, need client http://micropython.org/webrepl/
  import webrepl 
  print('import webrepl_setup once to set password')
  print('use http://micropython.org/webrepl/ to connect and use ws://192.168.1.9:8266/') 
  print('or use local webrepl.html, file:///C:/Users/pboud/micropython/webrepl-master/webrepl.html')
  # cannot use ws://192.168.1.9:8266/ directly in browser
  webrepl.start()


#########################################################
# deep sleep ESP32
# param is sec
#########################################################

#  pass pin list. set pin to low before deep sleep
def power_down(pins):
  print('turn all external components to off')
  for p in pins:
    p.off()

def go_to_deepsleep(sec):
  sleeptime_msec = sec * 1000 
  print('ESP32 will deep sleep for %d sec' %sec)
  led.on()
  power_down(pin_to_power_down) # all power pins

  deepsleep(sleeptime_msec)

#############################################
# watchdog. prevent hang
#############################################
def watchdog(sec): # tuple
  global repl
  print('\nwatchdog thread started for %d sec' %sec)
  sleep(sec)
  print('!!!!!watchdog popped. repl: ', repl)
  # prevent deep sleep if in REPL
  if repl:
    print('watchdog: repl is true, do not deep sleep')
    return()

  # increment RTC error counter
  v = read_RTC(4)
  v = v + 1
  set_RTC(4, v)

  try:
    blynk.notify('ECS: watchdog popped')
    s = ('%d %d %d: watchdog popped' %(mday, hour, minute)) # use time stamp vs simple random number
    blynk.virtual_write(vpin_terminal, s)
    oled.fill(0)
    oled.text("watchdog popped ", 0, 2)
    oled.show()
    sleep(3) # time to read
    sleep(3) # blynk to complete before deep sleep ?
  except Exception as e:
    print('watchdog: ', str(e))
  finally:
    go_to_deepsleep(sleep_sec_error)  

#####################################################
# start wifi
# https://docs.micropython.org/en/latest/library/network.html
# https://docs.micropython.org/en/latest/library/network.WLAN.html
#####################################################

def wifi_connect(ssid, psk):
    import network
    from time import sleep_ms
    i =0
    ok = True
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    print('set static IP')
    sta_if.ifconfig(('192.168.1.9', '255.255.255.0','192.168.1.1', '8.8.8.8'))
    sta_if.connect(ssid, psk)

    while not sta_if.isconnected():
      sleep_ms(300)
      i = i + 1
      if i >=10:
        ok=False
        break
         
    if ok == True: 
      sleep_ms(10)  
      print('\n\nconnected. network config:', sta_if.ifconfig())
      print ('status: ', sta_if.status()) # no param, link status
      print('ssid: ', ssid)
      print('rssi ', sta_if.status('rssi')) # no []
      return (sta_if) 
    else:
      print('cannot connect to %s' %(ssid))
      return(None)
# return None or sta_id



########################################
# blynk thread 
########################################

def blynk_thread(a):
  global blynk # access to publish
  print('\nBLYNK: starting ..', a)

  # call back, then initialization code
  
  
  ################################### 
  # define BLYNK CALL BACKS . seem to need to be in thread
  ###################################

  #########################
  # connect call back
  # read temp sensors and publish to blynk
  #########################
  
  @blynk.handle_event("connect")
  def connect_handler():
    global first_connect
    global update_done
    global temp_haut, temp_milieu # set in connect call back, used in main
    global oled
    global r
   
    print("   BLYNK: in connect call back")

    if first_connect: # avoid connect, disconnect
      print('   BLYNK: first connect')
      # do not send notif for each deep sleep
      #blynk.notify('ECS starting')
      #blynk.email('pboudalier@gmail.com', 'teleinfo', 'starting')
      first_connect = False


    ####################################
    # read all sensors
    ####################################

    print('   BLYNK: read sensors')

    (vcell, soc) = read_lipo_gauge(i2c)
    if vcell == None:
      print('   BLYNK: !! error lipo sensor')
    else:
      print('   BLYNK: vcell %0.1f, soc %0.1f'  %(vcell, soc))
    # also vbat from onboard ADC
    # vcell == None for error

    temp = read_temp(ds18b20_gpio)
    # temp == [] for error

    if temp != []:
      """
      how do I know which one is one ?
      looking at the data, should be as below
      """
      temp_haut = temp[1] 
      temp_milieu = temp[0]
      print('   BLYNK: temp haut %0.1f, temp milieu %0.1f'  %(temp_haut, temp_milieu))
    else:
      print(' BLYNK: !! error temp sensor')


    ########################################################
    # publish lipo to blynk
    # write to oled
    ########################################################
    
    print('sensor read, publishing ..')

    if (blynk.is_server_alive()) == True:

      # send notification and email for sensor first fail, or first recovered only, based on status stored in RTC memory
      # ie avoid flooding

      #########################
      # LIPO
      ##########################

      if vcell != None: # sensor OK
        blynk.virtual_write(vpin_vsoc, int(soc))
        oled.fill(0)
        oled.text(("vcell: " + str(vcell)), 0, 0)
        oled.text(("soc:   " + str(int(soc))), 0, 10)
        oled.text(("vbat:  " + str(vbat)), 0, 20)
        oled.show()
        sleep(3) # time to read
        
        if r.memory()[1] == sensor_failed: # we were in a sensor error state.
          print('send notification: recovered')
          blynk.notify('ECS: lipo sensor recovered: %s ' %(str(vcell)))
          blynk.email('pboudalier@gmail.com', 'ecs micropython lipo sensor recovered')
          # reset error condition in RTC memory
          set_RTC(1, sensor_ok)
          print ('lipo error status set to OK. RTC: ', r.memory())
        else:
          pass # status is OK and sensor read is OK

      else: # error lipo sensor vcell == None

        oled.fill(0)
        oled.text("lipo error ", 0, 16)
        oled.show()
        sleep(3) # time to read
        
        # increment RTC error counter
        v = read_RTC(3)
        v = v + 1
        set_RTC(3, v)

        # write error to blynk terminal at each failed read
        # write content of RTC error counters
        s= str(mday) + ' ' + str(hour) +':' + str(minute)
        s = ('%s: lipo sensor error' %s) # use time stamp vs simple random number
        print(s)
        blynk.virtual_write(vpin_terminal, s)
        s = 'counters: %s'%(str(r.memory()))
        print(s)
        blynk.virtual_write(vpin_terminal, s)  # b'\x01
        
 
        # update RTC flag
        if r.memory()[1] == sensor_ok: # we were in a sensor ok state.
          print('send notification: failed')
          blynk.notify('ECS: lipo sensor failed !! ')
          #blynk.email('pboudalier@gmail.com', 'ecs micropython: lipo sensor failed')
          
          set_RTC(1, sensor_failed)
          print ('lipo error status set to failed. RTC: ', r.memory())
        else:
          print('lipo sensor still failing')


      ########################################################
      # publish temp to blynk
      # write to oled
      ########################################################

      if temp != []: # temp sensor OK
        oled.fill(0)
        blynk.virtual_write(vpin_haut, temp_haut) # temp top, v43, red
        blynk.virtual_write(vpin_milieu, temp_milieu) # temp mid, v44, orange
 
        # write to blynk terminal, incl get time stamp(TZ) and flags
        s = ('%d/%d:%d mid %0.1f top %0.1f' %(mday, hour, minute, temp_milieu, temp_haut)) # use time stamp vs simple random number
        # write flag as well
        s1=r.memory() #  will print b'\x01\x01\x00\x00\x00'
        s1 = '%s %s %s %s %s' %(s1[0], s1[1], s1[2], s1[3], s1[4]) # str to print
        blynk.virtual_write(vpin_terminal, '%s %s ' %(s,s1))

        oled.text(("top: " + str(temp_haut)), 0, 0)
        oled.text(("mid: " + str(temp_milieu)), 0, 10)
        oled.show()
        sleep(3)

        if r.memory()[0] == sensor_failed: # we were in a sensor error state.
          print('send notification: recovered')
          blynk.notify('ECS: temp sensor recovered: %0.1f %0.1f ' %(temp_haut, temp_milieu))
          #blynk.email('pboudalier@gmail.com', 'ecs micropython temp sensor revovered')
          # reset error condition in RTC memory
          
          set_RTC(0,sensor_ok)

          print ('temp error status set to OK. RTC:', r.memory()) 
        else:
          pass # status is OK and sensor read is OK

      else: # temp sensor failed
        oled.fill(0)
        oled.text("haut failed", 0, 2)
        oled.text("milieu failed", 0, 14)
        oled.show()
        sleep(3) # time to read

        """
        would distort the graph
        blynk.virtual_write(vpin_haut, 100) # temp top, v43, red
        blynk.virtual_write(vpin_milieu, 100) # temp mid, v44, orange
        """

        # increment RTC error counter
        v = read_RTC(2)
        v = v + 1
        set_RTC(2, v)

        # write error to blynk terminal at each failed read
        s= str(mday) + ' ' + str(hour) +':' + str(minute)
        s = ('%s: temp sensor error' %s) # use time stamp vs simple random number
        print(s)
        blynk.virtual_write(vpin_terminal, s)
        s = 'counters: %s'%(str(r.memory()))
        print(s)
        blynk.virtual_write(vpin_terminal, s)  # b'\x01

        # only send notification and email for 1st fail
        if r.memory()[0] == sensor_ok: # we were in a sensor ok state.
          print('send notification: failed')
          blynk.notify('ECS: temp sensor failed !! ')
          #blynk.email('pboudalier@gmail.com', 'ecs micropython temp sensor failed')
          # reset error condition in RTC memory
          set_RTC(0, sensor_failed)
          print ('temp error status set to failed. RTC: ', r.memory())
        else:
          print('temp sensor still failing')


      print(r.memory())
      update_done = 1 # to signal ok to main thread. main waiting on this global var
      # could have had sensor error

    else: # blynk not alive

      print('   BLYNK: blynk server not alive, could not update')
      # maybe oled worked
      update_done = -1 # to signal blynk error to main thread. 

  print('   BLYNK: end connect call back')
  # end connect call back. update_done = 1 (sensor ok or nok) or -1 if blynk error
   
    
  @blynk.handle_event("disconnect")
  def disconnect_handler():
    print("   BLYNK: in disconnect call back")

  ################################### 
  # BLYNK initialization code connect and run
  ###################################

  print(' BLYNK: blynk.connect() before run loop')
  # connect default timeout 30sec
  if (blynk.connect(timeout=30)): # boolean
    print(' BLYNK: ***** blynk is connected *****')
  else:
    print('   BLYNK: !!!! cannot connect !!!!')
  
  if (blynk.is_server_alive()) == True:
    print('   BLYNK: server is alive')
  else:
    print('   BLYNK: server not alive, go to deep sleep')
    oled.fill(0)
    oled.text("blynk connect", 0, 0)
    oled.text("error", 0, 8)
    oled.show()
    sleep(5)
    
    go_to_deepsleep(sleep_sec_error)

  print('   BLYNK: call blynk.run endless loop. does not return')
  # blynk.run will make call back happen
  # need to call Blynk.run to have callback read start button value
  # and as Blynk.run does not return, need to start apps.
  try:
    blynk.run()
      
  except Exception as e: # notify error and deep sleep to retry
    print('   BLYNK: blynk.run thread exception %s', str(e))
    blynk.notify('micropython blynk.run exception: %s ' %(str(e)))
    blynk.email('pboudalier@gmail.com', 'ecs micropython blynk run exception', str(e))
    print('deep sleep sec: ', sleep_sec_error)
    
    go_to_deepsleep(sleep_sec_error)
# Blynk thread


####################################################
# read lipo gauge
#####################################################
def read_lipo_gauge(i2c):
  vcell = -1 # 
  soc = -1

  try:

    print('read lipo: power mosfet on')
    mosfet_pin.on()   # not needed powered on at init to make sure power is stable, init ok etc ..
    

    """
    use modified library. create i2c object in main, and pass to library
    can use same i2c for multiple sensors
    original library had hardcoded i2c pins for pyboard
    """

    m = max17043(i2c)

    for i in range(5): # multiple read to stabilize ?
      vcell = round(m.getVCell(), 1)
      soc = round(m.getSoc(), 0)
      print(vcell, soc)
      sleep_ms(500)

    print('vcell %0.1f, soc %0.0f: '% (vcell, soc))

    # print everything about the battery and the max17043 module
    # call the __str__ method
    #print(m)

    # restart the module
    #m.quickStart()

    # close the connection to the module
    #m.deinit()

    return(vcell, soc)

  except Exception as e:
    print('exception reading Lipo gauge ' , str(e))
    return(None,None)


##############################################
# read temp sensors
# DS18B20 aka dallas
# vcc 3 to 5V
# 4.7k resistor between vcc and data
##############################################
def read_temp(gpio):
  print('read all temp sensors on gpio ', gpio)

  try:

    dallas_power_pin.on() # power sensor
    sleep_ms(300)

    import onewire, ds18x20

    # the device is on GPIOx
    dat = Pin(gpio)

    # create the onewire object
    ds = ds18x20.DS18X20(onewire.OneWire(dat))

    # scan for devices on the bus
    roms = ds.scan()
    print('ds18b20 scan, found devices:', roms)

    temp = []
    ds.convert_temp()
    sleep_ms(750)
    for rom in roms: # read all sensors on this gpio bus
      """
      2 sensors on same bus (ie data GPIO). how do I know which one is one ?
      may be better to have each sensor on a separate bus. 
      """
      t = ds.read_temp(rom)
      t = round(t,1)
      #print('dallas: ', t)
      temp.append(t)
    
    dallas_power_pin.off()
    print(temp)
    return(temp) # seems should be interpreted as (mid, top)

  except Exception as e:
    print('exception reading temp sensors ' , str(e))
    return([])


##############################################
# sensors handled in connect call back
# wait until read and update, via global variable
# go to deep sleep or idle with repl
###############################################

def end_app(a):
  global repl # if not local to thread and update not seen by watchdog thread

  print('\nend app thread started: wait for connect Blynk call back to read and update sensors') # wait for sensor value update into blynk server
  while update_done == 0: # will be set to 1 or -1 for blynk error
    sleep(2)
    #print('update done ? ', update_done)
    print('=', end='')
  print('sensor updated, update_done: ', update_done)


  if update_done == 1: # OK
    oled.fill(0) # with black , 1 with white
    oled.text("Blynk OK", 0, 2) # X,Y
    oled.show()
    
  if update_done == -1: # blynk error
    oled.fill(0) # with black , 1 with white
    oled.text("Blynk error", 0, 2) # X,Y
    oled.show()
    

  # read test pin (pull up)
  # connect GPIO 15 to gnd to avoid any deep sleep. allow to reflash in peace
  if test_pin.value() == 0:
    print('==== > test pin is pulled LOW. no deep sleep, start repl and idle')
    start_repl()
    
    oled.text("REPL", 0, 12)
    oled.show()
    repl = True
    print('repl: ', repl)
    while True:
      sleep(10)  # idle forever. can update with webrepl

  else:

    oled.text("SLEEP", 0, 12)
    oled.show()

    print('==== > test pin is HIGH. deep sleep')
    print('disconnect from blynk and wifi ')
    blynk.disconnect()
    sleep(2)
    wifi.disconnect()
    sleep(1)

    print ('script execution time(ms): ', ticks_ms()-start_time)

    print('go to deep sleep until next measure ', sleep_sec_measure)
    go_to_deepsleep(sleep_sec_measure)

# end app

############################
# main
############################

# project meaudre, cloud server
# public blynk server

init_RTC([1,1,0,0,0])

blynk = blynklib.Blynk('128bf199aa8744f88a586beecb6b64d9')
print ('BLYNK: blynk on public server created: ' , type(blynk))

first_connect = True
update_done = 0 # global. set to 1 if OK or -1 if error in blynk connect call back
temp_haut = 0.0
temp_milieu = 0.0

########################################################
# i2c and oled init
# run before wifi and blynk, to provide feedbaks
########################################################

#https://github.com/micropython/micropython/tree/master/drivers/display

#There are two hardware I2C peripherals with identifiers 0 and 1. Any available output-capable pins can be used for SCL and SDA but the defaults are given below.
#https://docs.micropython.org/en/latest/esp32/quickref.html#hardware-i2c-bus


print('power oled with gpio')
oled_power_pin.on()
sleep(1) #race confition

print("start i2c and scan")
i2c = I2C(scl=Pin(scl), sda=Pin(sda))
#i2c = I2C(1,scl=Pin(scl), sda=Pin(sda), freq=4000000)
print('i2C CREATED, scan bus')

devices = i2c.scan()
if len(devices) == 0:
  print("no i2c devices")
else:
  print ("devices list: ", devices) 
  print ("devices in hexa")
  for x in devices:
    print (hex(x), end= ' ')
  print(' ')
"""
devices:  [54, 60]
list devices in hexa
0x36
0x3c
"""

# oled 60, 0x3c
print("create ssd1306 oled")
try:
  #https://randomnerdtutorials.com/micropython-oled-display-esp32-esp8266/
  #oled = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c)
  oled = ssd1306.SSD1306_I2C(128, 32, i2c)

  # display version and errors counters from RTC memory
  oled.fill(0) # with black , 1 with white
  oled.text("Pabou ECS v%s"%version, 0, 2) # X,Y
  s=r.memory() #  will print b'\x01\x01\x00\x00\x00'
  s = '%s %s %s %s %s' %(s[0], s[1], s[2], s[3], s[4]) # str to print
  print(s)
  oled.text("flag: %s" %s, 0, 20) # X,Y
  oled.show()
  sleep(3)

except Exception as e:
  print('Exception create oled ' , str(e))

###############################################
# start wifi
# credential for wifi stored in mynet.py
"""
net = [
['ssid1', 'pass1'] , \
['ssid2', 'pass2'] \
]
"""
###############################################

import mynet
print(mynet.net)

wifi_ok = False
for i in range(len(mynet.net)):
  print("\ntrying to connect to wifi %s ...\n\n" %(mynet.net[i][0]))
  wifi = wifi_connect(mynet.net[i][0], mynet.net[i][1])
  
  if wifi != None:
    (ip, _,_,_) = wifi.ifconfig()

    print('\n************** wifi connected **************\n')
    wifi_ok = True
    oled.fill(0)
    oled.text("Wifi:       OK", 0, 0)
    oled.text('rssi:       ' + (str(wifi.status('rssi'))), 0, 8)
    oled.text("sleep (mn): " + str(int(sleep_sec_measure/60)), 0, 24)
    oled.text("ip:" + ip, 0, 16)
    oled.show() 
    break

if (wifi_ok == False):
  print('could not connect to any wifi')
  print('deep sleep sec: ', sleep_sec_error)
  oled.fill(0)
  oled.text("Wifi not OK", 0, 0)
  oled.text("deep sleep", 0, 10)
  oled.show()
  sleep(3) # time to see
  
  go_to_deepsleep(sleep_sec_error)

else:
  # set local time from ntp server. 
  print('local time before ntp: ', localtime())

  for i in range(5): # retry in case of TIMEOUT

    try: # protect from timeout in ntp
  
      print('set time with ntp')
      ntptime.settime()
      (year, month, mday, hour, minute, second, weekday, yearday) = localtime()
      print('UTC time after ntp: ', localtime()) # tuple (year, month, mday, hour, minute, second, weekday, yearday)

      # adjust in code for TZ. RTC can only run in UTC
      t=mktime(localtime())
      t = t + 2*3600
      (year, month, mday, hour, minute, second, weekday, yearday) = localtime(t)
      print('local time after TZ: ', localtime(t))

      print('day: %d hour: %d mn: %d'%(mday, hour, minute ))

      break

    except Exception as e:
      print('exception in ntp ', str(e))
      # default value for time stamp, otherwize undefined
      (year, month, mday, hour, minute, second, weekday, yearday) = localtime()
      sleep(2)
  

    

########################################
# one thread in main, another as separate thread
##########################################

"""
print('start blynk thread')
_thread.start_new_thread(blynk_thread, ('pabou')) 
# block at blynk.run()
"""

print('start end app thread')
_thread.start_new_thread(end_app, ('pabou',))  # param need to be a tuple
# will wait for blynk to run and call deep sleep or idle

print('start watchdog thread')
_thread.start_new_thread(watchdog, (60,))  # param need to be a tuple

# run in main
blynk_thread(('pabou',)) # block at blynk.run() 


