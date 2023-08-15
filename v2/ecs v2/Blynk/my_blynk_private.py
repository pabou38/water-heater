
version = 2.3
# 9 juillet 2023 add wait_blynk, global to stop thread
# 12 juillet clean ctrlC
# stop_run moved in separate shared.py


# https://github.com/blynkkk/lib-python

################### LEGACY, PRIVATE ##############

# WINDOWS
# DEEP/Blynk/my_blynk_private.py
# DEEP/Blynk/my_blynk_new.py

# WINDOWS projects in DEEP/<project> 
#  so import ../Blynk

# MICROPYTHON projects in micropython/<project>
# sym link to micropython/MY MODULES 
# sym link to DEEP/Blynk

# LINUX
# HOME/Blynk/my_blynk_private.py
# HOME/Blynk/my_blynk_new.py
# projects in HOME/<project> , so import ../Blynk

import sys, random
from time import localtime, sleep, sleep_ms
import _thread
from machine import reset

# shared with disconnect. goblal to stop blynk.run thread
import shared

print("my blynk private v%0.1f" %version)

p = sys.platform

# ESP* client legacy library, as this code, should be in a windows dir, to be uploaded on ESP, and which is included in micropython sys.path


# import client legacy library

if p == 'esp8266':
  import blynklib_legacy_mpy as blynklib 
  print("running on esp8266. blynklib_mpy, ie frozen version. should be in sys.path")

if p == 'esp32':
  import blynklib_legacy_mp as blynklib 
  print("running on esp32. import blynklib_mp. should be in sys.path")

if p == 'linux':
  print("running on Linux. import blynklib_legacy_0_2_6 from ../Blynk/Blynk_client")
  # asume we are in APP/<project>. 
  sys.path.insert(1, '../Blynk/Blynk_client') # this is in above working dir 
  import blynklib_legacy_0_2_6 as blynklib # in Blynk

import blynktimer_legacy as blynktimer

# micropython v1.19 required mpy v6  
# xxd , on windows PS> format-hex *.mpy 00000000   4D 06 02 ...  0x4d (ASCII ‘M’)   2nd byte is version 6
# make sure byte code consistent with micropython

# blynklib_mp.py  blynklib_mpy.mpy
# either rename blynklib_mp.mpy to blynklib_mpy.mpy
# or delete blynklib_mp.py

# use mpy version of blynklib on esp8266 # .mpy version ok for esp8266 


####### 
# blynk.run as thread (ESP32, linux) or in main (ESP8266) and use timers
#######



def b_log(x):
  print('blynk log:' , x)
  pass

"""
blynk log: Connected to blynk server
blynk log: Authenticating device...

start blynk.run endless loop
blynk log: Access granted
blynk log: Heartbeat = 60 sec. MaxCmdBuffer = 1024 bytes
blynk log: Registered events: ['connect', 'disconnect', 'internal_rtc']

blynk log: Event: ['connect'] -> ()

blynk log: Event: ['write v14'] -> (14, ['0.019339999999999996'])

"""



connect_call_back_occured = False # in case needed to test . can also check .connected()
shared.stop_run = False
first_connect = True

######################
# create blynk object
######################

# 8089 13809
# 9444 13810  use for app
# 7443 13811  admin

def create_blynk(token, wifi = None, log = True):
  if wifi is None:
    # default server
    blynk_server = "192.168.1.206"
    blynk_port = 8089
  else:
    # get server from ssid
    ssid = wifi.config('ssid')
    print("getting blynk server from ssid" , ssid)
    if ssid in ["Freebox-382B6B"]:
      blynk_server = "paboupicloud.zapto.org"
      blynk_port = 13809
    else:
      blynk_server = "192.168.1.206"
      blynk_port = 8089

  # token in secret.py
  print ('\nBLYNK: create private server. auth token: ' , token, blynk_server, blynk_port)

  # ssl argument not available 
  # for Python v0.2.6
  # log is Blynk log. omit to get rid
  if log:
    blynk_con = blynklib.Blynk(token,server=blynk_server, port=blynk_port, heartbeat=60, log=b_log)
  else:
    blynk_con = blynklib.Blynk(token,server=blynk_server, port=blynk_port, heartbeat=60)

  #### connect call back patacaisse

  # when this module is imported
  # system call back defined here will be executed 
  # connect callback defined in main IS NOT executed ??

  # when this module runs as main
  # connect callback defined in main IS  executed and overwrite the on defined here

  ###################
  # system call backs defined in the context of create_blynk
  # define here if generic (no need to trigger specific processing)
  ###################
  
  
  #### connect #####
  @blynk_con.handle_event("connect")
  def connect_handler():
    global first_connect
    global connect_call_back_occured

    print("BLYNK: connect call back defined within create_blynk(). localtime: ", localtime())

    connect_call_back_occured = True

    if first_connect: # avoid connect, disconnect
      print('BLYNK: first connect')
      first_connect = False  

      # RTC sync request was sent
      print('BLYNK: sync RTC in first connect')
      blynk_con.internal("rtc", "sync")

  
  
  #### disconnect #####
  @blynk_con.handle_event("disconnect")
  def disconnect_handler():
    print("BLYNK: disconnect call back defined within create_blynk(): localtime ", localtime())

  # https://docs.micropython.org/en/latest/library/time.html
  
  #### RTC #####
  @blynk_con.handle_event('internal_rtc')
  def rtc_handler(rtc_data_list):
    print("BLYNK: rtc call back defined within create_blynk(): localtime ", localtime())
    print("BLYNK: rtc from server ", rtc_data_list)
    # datetime not available in micropython
    #hr_rtc_value = datetime.utcfromtimestamp(int(rtc_data_list[0])).strftime('%Y-%m-%d %H:%M:%S')
    #print('Raw RTC value from server: {}'.format(rtc_data_list[0]))
    #print('Human readable RTC value: {}'.format(hr_rtc_value))
  
  return(blynk_con)


######################
# connect to blynk server
######################

def connect_blynk(blynk_con):

  ### looks like return code from connect is not reliable. can return None. check connected explicitly

  timeout=30
  print("BLYNK: connecting to server. timeout %d" %timeout)
  ret= blynk_con.connect(timeout=timeout)
  print("BLYNK: blynk connect returned: %s" %ret)
  return(ret)



######################
# wait for blynk to be connected
# test not blynk_con.connected()
######################

def wait_blynk(blynk_con):
  i = 0
  max = 30

  while not blynk_con.connected():

    i = i + 1
    if i > max:
      print("BLYNK: blynk server not connected after %d wait" %i)
      return(False)
    else:
      sleep(1)

  print("BLYNK: blynk.connected: %s" %blynk_con.connected())
  return(True)

###################  
# .run() endless loop
# run in main or separate thread
# monitor stop_run global variable (just exit while loop)
####################

#####################
# case 2: blynk.run in main
# only case would be ESP8266, no thread module ??
# use timers to process sensor
# nothing else in main
#my_blynk_private.run_blynk(blynk_con, log = log)
#####################

def run_blynk(blynk_con):
  global stop_run
  print("\nBLYNK: start blynk.run endless loop")
  while True:
    # blynk.run will make call back happen need to call Blynk.run to have callback read start button value
    # need while true around .run()
    try:
      blynk_con.run()
      #timer.run()

      # check global set in main
      if shared.stop_run:
        print("BLYNK: in blynk run thread. stop_run is True. must stop")
        break

      # is this needed to make sure the code on ESP32 can be interupted in vscode or Thonny
      sleep_ms(5)

    except Exception as e: 
      print('BLYNK: blynk.run exception %s', str(e))

      try:
        reset()
      except Exception as e:
        pass

  # while true
  # break while true based on global var
  print("blynk run endless loop thread stopping ")

print("my_blynk_private: ", __name__)

if __name__ == "__main__":

  print("\n!!!!running my_blynk_private as main (standalone)")

  print("when used in app, ie my_blynk_private is imported") 
  print("<home>/micropython/<app>/Blynk/ is a sym link (to be created) pointing to <home>/Blynk/Blynk_client in windows file system ")
  print("/micropython/<app>/Blynk/ is to be copied to ESP32 file system as /Blynk")
  print('esp32 code should add /Blynk in path: sys.path.append("/Blynk")')

  """
  when uses a main, ie as stand alone module, to test my_blynk_private itself
  run from Blynk dir, and uses test vpin and secret located in Blynk

  when used in app, ie my_blynk_private is imported
   Windows: 
    <home>/micropython/<app>/Blynk/ is a sym link (to be created) pointing to <home>/Blynk/Blynk_client in windows file system 
      ie: home/Blynkto accumulate all edits into a master version

    ESP32:
      /micropython/<app>/Blynk/ is to be copied to ESP32 file system as /Blynk
      esp32 code should add in path: sys.path.append("/Blynk")


   import vpin and secret done in app, and use file in app directory (not from Blynk)

  """


  ##########
  # wifi
  ##########

  sys.path.append("../my_modules")
  import my_wifi

  own_ip="192.168.1.3" # static
  own_ip=None  # dhcp

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


  import vpin_test # application specific, in app directory
  import secret_test # application agnostic, in my_modules


  # token for both legacy and new
  blynk_token = secret_test.blynk_token_cloud

  # cannot use log=None. create object with or without log defined is done in my_blynk
  blynk_con = create_blynk(blynk_token, log=True)

  stop_run = False # monitored by thread below

  _thread.start_new_thread(run_blynk, (blynk_con,))


  #######################
  # connect call back defined in main  # vs the one defined create_blynk ?

  # could also leave in create_blynk (app agnostic) and rely on global variable if the only thing we need is the fact it happened
  # or check is_connected() ? 
  #######################

  #### connect #####
  @blynk_con.handle_event("connect")
  def connect_handler():
    global first_connect
    global connect_call_back_occured

    print("BLYNK MAIN: connect call back defined in MAIN. localtime: ", localtime())

    connect_call_back_occured = True

    if first_connect: # avoid connect, disconnect
      print('BLYNK MAIN: first connect')
      first_connect = False  


  print("connect to blynk")
  ret = connect_blynk(blynk_con)
  print("connect returned %s" %ret)

  print("wait for blynk to connect")

  # test  blynk_con.connected()
  ret= wait_blynk(blynk_con)
  if ret == False:
    print("cannot connect to blynk. EXIT as we are in test mode")
    sys.exit(1)

  else:
    print("\n!!! Blynk connected. connect call back occured %s" %connect_call_back_occured) 


  control_vpin = vpin_test.vpin_control # control
  display_vpin = vpin_test.vpin_non_push_display # display non push

  ###############
  # widget call backs
  # could be defined in my_blynk module, or here in main 
  # typically in main as main logic need access to update event and value
  # after blyn_con is created

  # control: decorator  "write V%d   
  # display non push: decorator 'read V%d and call back wirtual_write
  # NOTE: display push: no call back. logic does wirtual_write
  ##############

  ### control widget
  # define where the update is needed (eg main if main logic need access to update event and value)
  s = "write V%d" %control_vpin
  @blynk_con.handle_event(s)
  def write_virtual_pin_handler(pin, value):
      global flag
      print("BLYNK: call back control widget", pin, value)
      flag = value[0] # str
      flag_int = int(value[0])

  ### display widget
  # FOR NON PUSH display widget
  # will be called based on timer, set in widget itself
  @blynk_con.handle_event('read V' + str(display_vpin))
  def read_virtual_pin_handler(pin):
      i = random.randint(0, 255)
      print("BLYNK: call back non push display widget %d. rand %d" %(pin,i))
      blynk_con.virtual_write(pin, i)


  # sync, ie data needed for processing loop
  # for control widgets
  #### WARNING: seems need to be done AFTER widget call back defined
  blynk_con.virtual_sync(control_vpin) 
  
  
  colors = {'#FF00FF': 'Magenta', '#00FF00': 'Lime'}

  while True:

      # uses vpin_test
      try:
        blynk_con.virtual_write(vpin_test.vpin_display, 1000)
        blynk_con.virtual_write(vpin_test.vpin_terminal, "test blynk private")
        blynk_con.set_property(vpin_test.vpin_display, 'color',  '#FF0000')
        blynk_con.set_property(vpin_test.vpin_display, 'label',  'display')

        try:
          blynk_con.notify('blynk private notification')
        except:
          pass

        try:
          blynk_con.email('pboudalier@gmail.com', 'blynk private email')
        except:
          pass

        sleep(5)

      except KeyboardInterrupt:
        s = "got KeyboardInterrupt. disconnect and reset"
        print(s)
        
        blynk_con.disconnect(err_msg=s) # blynk log: [ERROR]: KeyboardInterrupt: disconnect blynk
        sleep(2)
        stop_run = True # global in context of this module
        sleep(2)
        wifi.disconnect() 

        # reset or exit
        sys.exit(1)

      except Exception as e:
        s = "exception non keyboard interupt %s. disconnect and reset" %str(e)
        print(s)

        blynk_con.disconnect(err_msg=s)
        sleep(2)
        stop_run = True # global in context of this module
        sleep(2)
        wifi.disconnect()

        # reset or exit
        sys.exit(1)



      