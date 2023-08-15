
import uping
# https://forum.micropython.org/viewtopic.php?t=5287

import deep_sleep
from time import sleep


def ping_ip(ip):

    (a,b) = uping.ping(ip, count=2, timeout=5000, interval=10, quiet=True, size=64)
    # @return: tuple(number of packet transmitted, number of packets received)

    #print(a,b)
    if a!= b:
        return(False)
    else:
        return(True)


#################
# ping thread
# pass wifi connection, used by disconnect
#################

def ping_thread(ip, d, logging, wifi):
    print("start ping thread", ip, d)

    while True:
        print("*", end='')

        ret = ping_ip(ip)
        if ret == False:
            s = "ping failed. clean and exit"
            print(s)
            logging.error(s)

            deep_sleep.disconnect_and_reset(s,wifi)

        else:
            sleep(d)
			
    
if __name__ == "__main__":
    print("ping")

    ip = "192.168.1.1"
    ret = ping_ip(ip)
    print("ping returned: %s" %ret)







