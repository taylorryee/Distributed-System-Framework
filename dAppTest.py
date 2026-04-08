from myTest import dApp
import time
import redis


if __name__ == '__main__':

    appOne = dApp("appOne")
    appTwo = dApp("appTwo")
    appOne.redis.flushdb()
    
    
    appOne.new_parm("parmOne","valOne")
    print(appOne.parms["parmOne"].value,"parm one value")

    appTwo.new_parm("parmOne","valTwo")
    time.sleep(1)
    print(appTwo.parms["parmOne"].value)

    appTwo.update_parm("parmOne","valTwo")
    time.sleep(1)

    print(f"updated appTwo value:{appTwo.parms["parmOne"].value}")
    print(f"updated appOne value:{appOne.parms["parmOne"].value}")
    
    

    




