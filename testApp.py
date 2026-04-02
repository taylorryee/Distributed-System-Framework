
import os, random, time
from datetime import datetime

from BaseApp import BaseApp, BaseTrace


class MyApp ( BaseApp ):

    CAT = "parm"
    NAME = "yoyo"
    NAME2 = "Dumbo"
    
    def __init__(self):
        print ( 'MyApp init..........')
        #self.servant = "MyTestApp"
        
        # Application level ARGS
        self.argParser = BaseApp.AppArgs()
        self.argParser.add_argument('--dSvnt', type=str, default=None, help='Test to send messages to this servant') #Add a destinatino servant arg
        self.argParser.add_argument('--httpPort', type=int, default=None, help='HTTP Port to service Web Requests')#Add arg for http port
        BaseApp.__init__(self)



        self.appStartupFunc ( self.myStart ) #Stores the myStart callback in self.cb. Will use later when we do app.run()
        
        
        
    def myStart ( self):
        self.log (BaseTrace.TRACE_APP, 'MyApp START.......%s' % self.args)    

         
        self.p1 = self.parm ( self.CAT, self.NAME) #Create 3 Parm objects - corresponding with redis keys parm.yoyo, parm.Dumbo, and NoParm.Exists - adds these parm objects to redis up intiliztion
        self.p2 = self.parm ( self.CAT, self.NAME2)

        self.p3 = self.parm ( 'NoParm', 'Exist', 'Just the def value' )
        self.linkNVS ( self.CAT, self.NAME, self.nvsLinkTest ) #Adds listener to parm.yoyo and adds callback nvsLinkTest if redis value changes at parm.yoyo
        
        self.dSvnt = self.args.dSvnt
        self.log (BaseTrace.TRACE_APP,"Test dSvnt[%s]" % self.dSvnt )
        

        
        self.startTicker ( 5.3, self.myTicker, 'myContext' )
        self.startTicker ( 12.01, self.myTicker2 )

    def nvsLinkTest ( self, cat, name, val ):
        self.log (BaseTrace.TRACE_APP, "NVS Link Update [%s:%s] val[%s]" % ( cat, name, val ))
        if self.args.httpPort is not None:
            webEvent = {
                    'timestamp': time.strftime("%H:%M:%S"),
                    'value': val
                }
            self.webNotifySSE(webEvent)

    def myTicker(self, cntx): #Runs every 5 seconds
        print("TICKER 1",flush=True)
        self.log (BaseTrace.TRACE_APP,'MyTicker %s' % cntx)
        self.log (BaseTrace.TRACE_APP,'GetNVS [%s:%s]...[%s:%s]' % (self.CAT, self.NAME, self.getNVS ( self.CAT, self.NAME), self.p1.value()  ) )
        self.log (BaseTrace.TRACE_APP,'GetNVS [%s:%s]...[%s:%s]' % (self.CAT, self.NAME2, self.getNVS ( self.CAT, self.NAME2), self.p2.value()  ) )
        self.log (BaseTrace.TRACE_APP,'GetNewParm [%s]' % self.p3.value() )
        
        
    def myTicker2(self, cntx): #Runs every 12 seconds
        print("TICKER 2",flush=True)
        self.log (BaseTrace.TRACE_APP,'MyTicker2 %s' % cntx)
        value = random.randint ( 1, 100 )
        self.log (BaseTrace.TRACE_APP,'SetNVS [%s:%s]...[%s]' % (self.CAT, self.NAME, value ) )
        self.setNVS ( self.CAT, self.NAME, value ) #Sets redis key parm.yoyo to random value -> this should trigger the listener we added which will run the callback nvsLinkTest which will send this value to 
        #our frontend client. We have another callback in place from when we intilized Parm parm.yoyo which would update the local value of the Parm object p1 to new redis value. 
        
        value = random.randint ( 1, 100 ) 
        self.log (BaseTrace.TRACE_APP,'SetNVS [%s:%s]...[%s]' % (self.CAT, self.NAME2, "DumbVal%s" % value ) )
        self.setNVS ( self.CAT, self.NAME2, value )#We now update the other Parm object "parm.Dumbo". Here we did not add a seperate listener so it only runs the Parm object callback that updates its value. 
        
        print("GOT HERE LETS GOO",flush=True)
        msg = {}#Test rabbitmq queue message system
        msg['val'] = self.servant
        self.msgSend ( "HelloFrom%s" % self.servant, msg, self.dSvnt)
        
        #self.log (BaseTrace.TRACE_APP,'MyTraceLvl[%s]' % self. traceLevel.value() )
        
        # test insert into db
        val = random.randint ( 1, 10 )
        s = 'INSERT INTO GARY (value) VALUES (%s)' % val

        self.log ( BaseTrace.TRACE_APP, "Test insert[%s]" % s )
        # Looks like SQL Lite can't open db in diff thread
        self.db = self.get_db()
        self.db.execute(s)
        self.db.commit()
        self.db.close()

        

        
            

if __name__ == '__main__':
    app = MyApp()
    app.run()
