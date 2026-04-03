from myTest import dApp
import time



if __name__ == '__main__':
    app2=dApp()
    app = dApp()
    app.new_parm("boi","1738")

    print(app.parms["boi"].value,flush=True)
    app2.new_parm("boi","new value")
    time.sleep(1)
    print(app.parms["boi"].value,flush=True)



