from myTest import dApp
import time
import redis


if __name__ == '__main__':

    app2=dApp()
    app = dApp()
    app.redis.flushdb()
    app2.redis.flushdb()
    app.new_parm("boi","yeslawd")
    print("1",flush=True)
    time.sleep(1)
    app2.new_parm("boi","uhh why")
    print("2",flush=True)
    print(app2.parms["boi"].value,flush=True)

    print(app.parms["boi"].value,flush=True)
    




