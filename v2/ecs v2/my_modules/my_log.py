
import logging 
from time import localtime

# from micropython-lib-master  a single logging.py vs logging dir
# https://github.com/micropython/micropython-lib/tree/master/python-stdlib/logging/examples

def get_stamp():
# # set by ntp, but still UTC, TZ
  (year, month, mday, hour, minute, second, weekday, yearday) = localtime()
  s = "%d %d:%d" %(mday, hour, minute)
  return(s)


def get_log(app, level = "debug"):

    print("init log. app %s, level %s" %(app, level))
    if level == "debug":
        logging.basicConfig(level=logging.DEBUG) #  will display on stdout
    elif level == "info":
        logging.basicConfig(level=logging.INFO) #  will display on stdout
    elif level == "warning":
        logging.basicConfig(level=logging.WARNING) #  will display on stdout
    elif level == "error":
        logging.basicConfig(level=logging.ERROR) #  will display on stdout
    elif level == "critical":
        logging.basicConfig(level=logging.CRITICAL) #  will display on stdout
    else:
        print("%s unknown" %level)
        return(None)

    # can use logging.info
    logging.info("ecs v2 starting (using logging.info)") 
    # INFO:root:remote PZEM starting

    # or specific log.info
    log = logging.getLogger(app)
    log.info("creating logger for app %s" %app)
    # INFO:pzem:starting
    return(log)

"""
# same info, just formatted
class MyHandler(logging.Handler):
    def emit(self, record):
        print(record.__dict__)
        print("levelname=%(levelname)s name=%(name)s message=%(message)s" % record.__dict__)


logging.getLogger().addHandler(MyHandler())
logging.info("remote PZEM starting") 
# levelname=INFO name=root message=remote PZEM starting
"""

#######################
# write log into disk for futher analysis
# SHOULD NOT crash
# WARNING. prevent vscode pymakr to erase it on flash because it does not exist on windows when reflashing
######################
def crash(s):

    print("appending to crash file ", s)
    # Note that the default mode when opening a file is to open it in read-only mode, and as a text file. Specify 'wb' as the second argument to open() to open for writing in binary mode, 
    # and 'rb' to open for reading in binary mode.
    with open("crash.txt", "a") as f:
        f.write(s+'\n')

    with open("crash.txt", "r") as f:
        print("crash file content", f.read())


