from myTest import dApp

class Test(dApp):
    def __init__(self):
        super().__init__() #using super intilizes a chain if say dApp had a parent it would intilze dApps parenta s well
    
if __name__ == '__main__':
    app = Test()
    app.set_local("fag","bag")
    app.get_local("fag")
