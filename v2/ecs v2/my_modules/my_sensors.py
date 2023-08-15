
import onewire, ds18x20
from pb_max17043 import max17043


from machine import Pin
from utime import sleep_ms


##############################################
# DS18B20 aka dallas 
# vcc 3 to 5V 
# 4.7k resistor between vcc and data
# arg is a GPIO number. Pin object created inside
# nb (of sensor) not really used
# return list
##############################################

def read_dallas(gpio, nb=2):

  print('read %d temp sensors on gpio %d' %(nb, gpio) ) # nb not used

  nb_try = 5

  i = 0

  dat = Pin(gpio, Pin.OUT)
  # create the onewire object
  ds = ds18x20.DS18X20(onewire.OneWire(dat))

  while True:

    try:
  
      # scan for devices on the bus
      roms = ds.scan()
      print('ds18b20 scan, found devices: ', roms)

      temp = []
      ds.convert_temp() 
      # Note that you must execute the convert_temp() function to initiate a temperature reading, then wait at least 750ms before reading the value.
      sleep_ms(750)
      
      for rom in roms: # read all sensors on this gpio bus
        
        #2 sensors on same bus (ie data GPIO). how do I know which one is one ? . may be better to have each sensor on a separate bus. 
        
        t = ds.read_temp(rom)
        t = round(t,1)
        #print('dallas: ', t)
        temp.append(t)
      
      print('temp array: ' , temp)

      if len(temp) != nb:
        return(temp) # handle error later
      else:
        return(temp) # which is which ? seems should be interpreted as (mid, top)

    except Exception as e:
      print('exception reading temp sensors ' , str(e))

      i = i + 1
      if i > nb_try:
        print("temp sensor: give up, too many errors")
        return([])
      else:
        sleep_ms(500)
        # try again
	
	
####################################################
# read lipo gauge
#####################################################
def read_lipo_gauge(i2c):
  vcell = -1 # 
  soc = -1

  try:
    print('read lipo gauge')
    sleep_ms(300)
    """
    use modified library. create i2c object in main, and pass to library
    can use same i2c for multiple sensors
    original library had hardcoded i2c pins for pyboard
    """
    m = max17043(i2c)

    for _ in range(5): # multiple read to stabilize ?
      vcell = round(m.getVCell(), 1)
      soc = round(m.getSoc(), 0)
      #print(vcell, soc)
      sleep_ms(500)

    print('Lipo vcell %0.1f, soc %0.0f: '% (vcell, soc))
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


if __name__ == "_main__":

  gpio_temp = 10


  l = read_dallas(gpio_temp, nb=2) # Pin created in function
  if l != []:
      print(l)
  else:
    print('error temp')