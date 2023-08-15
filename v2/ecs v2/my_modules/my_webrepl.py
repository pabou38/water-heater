import webrepl

from utime import sleep
import os, sys

##################################################
# webrepl
# expect webrepl_cfg.py. should be synched with the rest of the project

##################################################

#webrepl_cfg.py
#PASS = 'meaudre'

def start_webrepl(log = None):

    s = "start webrepl"
    print(s)
    if log is not None:
        log.info(s)

    f = "/webrepl_cfg.py"
    try:
        os.stat(f)
        print("%s exits" %f)

    except OSError:
        s = "WARNING!!: %s does not exist" %f
        print(s)
        if log is not None:
            log.error(s)
        return(False)
    
    # need to import once webrepl_setup from a usb/ttl connection to set password
    # creates webrepl_cfg.py (not visible in uPyCraft, visible w: os.listdir()

    # cannot just browse to IP, need client http://micropython.org/webrepl/ 
    # web client from https://github.com/micropython/webrepl 
    # (hosted version available at http://micropython.org/webrepl)

    # The web client has buttons for the corresponding functions, 
    # or you can use the command-line client webrepl_cli.py from the repository above.

    print('import webrepl_setup once to set password')

    print("use WebREPL server started on http://192.168.1.178:8266/ and use ws://192.168.1.9:8266/")
    print('or use http://micropython.org/webrepl/ to connect and use ws://192.168.1.9:8266/') 
    print('or use local webrepl.html, file:///C:/Users/pboud/micropython/webrepl-master/webrepl.html')

    print("cannot use ws://192.168.1.9:8266/ directly in browser")

    webrepl.start() # return None

    #WebREPL server started on http://192.168.1.178:8266/
    #Started webrepl in normal mode

    # WebREPL connection from: ('192.168.1.19', 60214)
    # dupterm: EOF received, deactivating

    return (True)



############################################
# active loop after webrepl started
# feed dog is already started

#############################################

def in_repl(wdt=None):
    try:
        while True:
            sleep(10)
            #print("repl", end='')
            if wdt is not None:
                wdt.feed()

    except KeyboardInterrupt:  # while sitting in webrepl idle
        # since this is caugth, not getting a >>> usable to enter command ??
        s= "%s: got KeyboardInterrupt" %str(e)
        print(s)

        # but when ctrl C is used in WEBREPL console
        #   - get  >>> 
        #     wdt will pop and reset if not delt with
        #     cannot enter command (typing is cached until uncaugh CTRL C), which sys.exit
        #        

        # CTRL C used in vscode is OK. get >>> and reflash (I guess wdt is stopped by vscode ? or else just power off)

        while True:
            try:
                # stays there after a webrepl CTRL C to do file transfert
                if wdt is not None:
                    wdt.feed()
                    print("dog fed. file transfert available. hit CTRL C again to sysexit to (web)REPL prompt")
                # in this state, can do file transfert without fearing the dog, but cannot type command
                sleep(30)

            except KeyboardInterrupt: # or do not even bother to catch

                print("===> 2nd KeyboardInterrupt. sys.EXIT for good to (web)REPL prompt (can enter). beware wdt will reset anytime")
                sys.exit(1)
                # get >>> on webrepl. can type and do machine.reset or wait for wdt to reset anyway

   


if __name__ == "__main__":
    print("start webrepl")

    ret = start_webrepl()

    #WebREPL server started on http://192.168.1.178:8266/
    #Started webrepl in normal mode

    # use client to connect to IP:8266
    # repl output appears ; copy file to/from esp32

    print("returning from webrepl", ret)

    in_repl(wdt=None)

      