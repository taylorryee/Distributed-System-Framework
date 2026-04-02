from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import sqlite3
import json
import os
import threading
import time
import pika
import redis
import os
import argparse
import random
from datetime import datetime


sse_clients = []
sse_lock = threading.Lock()

class BaseTrace(object):
    TRACE_SYS = 5
    TRACE_APP = 10
    TRACE_OFF = 50
    TRACE_ERROR = 100
        
class BaseApp(object):

    ## Custom argument class so we can default to have SYSTEM level arguments
    class AppArgs (argparse.ArgumentParser):
        def __init__(self):
            argparse.ArgumentParser.__init__(self)
            # System Level arguments
            self.add_argument('--servant', type=str, default=None, help='Override default Servant ID') #defines a "--servant" arguement


    # Our Hot Update Parameter Class
    class Parm(object): #A Parm object is an object that is managed by its "master" BaseApp instance. It represents a single key,value inside global redis store
        def __init__(self, master, cat, name, defVal ): #master is BaseApp instance,
            self.cat = cat
            self.name = name
            self.defVal = defVal
            self.master = master
            master._nvsAddCallback ( cat, name, self._newValue )#This runs once when you intilize your Parm object - it adds a listener to redis for this key and adds a callback to newValue if a change is found. 
            #This means that this local value of Parm auto updates the current redis value by callback. 
            self.val = master.getNVS ( cat, name )#Sets value of your Parm object to corresponding value inside redis
            master.log (BaseTrace.TRACE_SYS,"PARM[%s:%s] CURR VAL[%s]" % ( cat, name, self.val ))
            if self.val is None:#Upon intilization if the value did not exist in redis - you set the value in redis to your defVal and then you set the local Parm object value to defVal. 
                if defVal is not None:
                    master.setNVS ( cat, name, defVal )
                    self.val = defVal
            else:
                self.val = self._convertVal ( self.defVal, self.val )#Otherwise if it did exist you convert your val to corresponding type of your defVal. 
            
            
        def _newValue(self, cat, name, val):
            # Redis always store value as STRING
            val = self._convertVal ( self.defVal, val )
            self.val = val
            self.master.log (BaseTrace.TRACE_SYS, "NewParmVal [%s:%s][%s:%s]->[%s]" % ( self.cat, cat, self.name, name,  self.val ))
            
        def _convertVal ( self, defVal, val ):
            if self.defVal is not None:
                # Convert it
                if isinstance(self.defVal, int):
                    val = int(val)
                elif isinstance(self.defVal, float):
                    val = float(val)
            return val
            
        def value(self):
            return self.val
            


    def __init__(self ): #intilizes a BaseApp instance

        if not hasattr(self, 'argParser'):#Check if someone already created a custom argument parser and set it. If not use default AppArgs parser. Ex)If someone creates a subclass using BaseApp and they define argParser than their custom
            #defintion would ovveride AppArgs. 
            self.argParser = self.AppArgs()
        self.args = self.argParser.parse_args()
        
        if self.args.servant is not None: #Gotta add case for no servant arguement - maybe a default worker id or make it a required arugement
            self.servant = self.args.servant
        self.log (BaseTrace.TRACE_SYS,'BaseAPP INIT.....Servant [%s]' % self.servant)
        self.tickerId = 0
        self.startCB = None
        self.nvs = None
        self.parmTable = {}


    
    

        
    def run(self):
        # Start Message QUEUE in background thread
        self.log (BaseTrace.TRACE_SYS,'BaseApp RUN......Start Servant QUEUE [%s]' % self.servant)
        self.msgQThread = threading.Thread(target=self.consume_queue, daemon=True)
        self.msgQThread.start()
        
        
        # Connect to DB
        self.db = self.get_db()

        
        # Start Redis listener in background thread
        self.log (BaseTrace.TRACE_SYS,'Start Servant NVS [%s]' % self.servant)
        
        startNvs = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        try:
            startNvs.config_set('notify-keyspace-events', '$K')
            self.log (BaseTrace.TRACE_SYS,'[REDIS] READY !!!!')
        except Exception as e:
            self.log (BaseTrace.TRACE_SYS, '[REDIS] Failed (may already be set): [%s]' % e)
        self.nvsPubSub = startNvs.pubsub()

        self.log (BaseTrace.TRACE_SYS,'Start Servant NVS Done and start thread[%s]' % self.servant)  
        self.nvs = startNvs
        # self.nvsThread = threading.Thread(target=self.listen_redis, daemon=True)
        # self.nvsThread.start()
        
        # App base parms for servant
        # Servant TRACE level
        self.traceLevel = self.traceLevel = BaseTrace.TRACE_APP
        # Call startup method for the app if registered
        if self.startCB is not None:
            self.startCB()
    
        #Server listens for requests and creates handler object upon request, handler processes the request
        #Creates custom HTTP server - base python server listens for requests and uses a handler to deal with requests(only accepts port and handler input)
        #We want to have access to our main app as well so that the handler can actually have access to our main app instance and all its methods. 
        class MyThreadingHTTPServer(ThreadingHTTPServer):
            def __init__(self, *args, **kw): #*args means any number of position args ie: 1,2,5, **kw means any number of keyword args ie:name="taylor"

                # Set my context
                if len(args) >= 3:
                    self.master = args[2]
                    self.master.log (BaseTrace.TRACE_SYS, "MyThreadingHTTPServer..Init [%s] [%s] lenArgs[%s] typeArgs[%s]" % ( args, kw, len(args), type(args) ))
                else:
                    self.master = None
                    print ( "MyThreadingHTTPServer..NoBaseApp arg !!!! [%s] [%s] lenArgs[%s] typeArgs[%s]" % ( args, kw, len(args), type(args) ))
                    

                ThreadingHTTPServer.__init__(self, *args, **kw)
        
        # If our APP wants to handle HTTP request
        # Start a thread for HTTP handler which passes our BaseApp context as the 3rd arg
        if self.args.httpPort is not None:
            self.log (BaseTrace.TRACE_SYS,'Start HTTP Server on http://127.0.0.1:%s' % self.args.httpPort)
            MyThreadingHTTPServer(('127.0.0.1', self.args.httpPort), self.Handler, self).serve_forever()
        
        
        
    def appStartupFunc ( self, startCB ):
        self.startCB = startCB
        
        
    def setNVS ( self, cat, name, value ):
        key = '%s.%s' % ( cat, name )
        self.log (BaseTrace.TRACE_SYS,'SetNVS Val[%s] = [%s]' % ( key, value) )
        self.nvs.set(key, value)
        
    def getNVS ( self, cat, name ):
        key = '%s.%s' % ( cat, name )
        val = self.nvs.get(key)
        self.log (BaseTrace.TRACE_SYS,'GetNVS Val[%s] = [%s]' % ( key, val) )
        return val
        
    def parm ( self, cat, name, defVal=None):
        p = self.Parm ( self, cat, name, defVal )
        return p
        
    def linkNVS ( self, cat, name, callback ):
        self._nvsAddCallback ( cat, name, callback )
        
    def _nvsAddCallback ( self, cat, name, callback ):#stores callback and subscribes to Redis notifications
        key = '%s.%s' % ( cat, name )
        if not key in self.parmTable:
            self.parmTable[key] = []
        self.parmTable[key].append ( callback )
        self.nvsPubSub.psubscribe(**{"__keyspace@0__:%s" % key: self.nvsHandler}) #“Subscribe to notifications for this Redis key, and when a message comes in, send it to self.nvsHandler.”
        self.nvsPubSub.run_in_thread(sleep_time=0.01)#This starts a background thread that listens for pub/sub messages.
        
        
    def nvsHandler(self, msg): #runs when a watched key changes, fetches the new value, and calls all registered callbacks
        DATA_KEY = "pattern"
        PREFIX = "__keyspace@0__:"
        self.log (BaseTrace.TRACE_SYS,"NVS Handler %s" % msg )
        if DATA_KEY in msg:
            val = msg[DATA_KEY]
            self.log (BaseTrace.TRACE_SYS,"Data [%s]" % val )
            i = val.find ( PREFIX )
            if i >= 0:
                key = val[i + len(PREFIX):]
                self.log (BaseTrace.TRACE_SYS, "NvsChanged[%s]" % key )
                elems = key.split('.')
                if len(elems) == 2:
                    cat = elems[0]
                    name = elems[1]
                    val = self.getNVS ( cat, name )
                    key = '%s.%s' % ( cat, name )
                    self.log (BaseTrace.TRACE_SYS, "ReadNVS[%s:%s] Val[%s]" % ( cat, name, val ))
                    if key in self.parmTable:
                        for callback in self.parmTable[key]:
                            callback(cat, name, val)
                    else:
                        self.log (BaseTrace.TRACE_SYS,'NVS for unknown parm[%s]' % key )


    def msgSend ( self, service, data, servant=None ):
    
        ## NEED to Map Service to Servant
        ## Simple Dictionary ("SERVICE1":"servantXYZ", "NEW SERVICE":"servvant123"}
        # Store in a json file and load it in startup
        
        hdr = {}
        hdr['service'] = service
        hdr['origServant'] = self.servant
        hdr['destServant'] = servant
        
        self._msgSend ( servant, hdr, data )
        

    def _msgSend ( self, servant, hdr, data ):
        msg = {}
        msg['header'] = hdr
        msg['data'] = data
        
        message = json.dumps(msg)
        self.msgChannel.basic_publish(
            exchange='',
            routing_key=servant,
            body=message,
            properties=pika.BasicProperties(delivery_mode=2) )
        self.log (BaseTrace.TRACE_SYS, "Send MSG [%s][%s]->[%s]"  % ( hdr, data, servant) )

    # def _msgSend(self, servant, hdr, data):
    #     connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    #     channel = connection.channel()

    #     msg = {
    #         "header": hdr,
    #         "data": data
    #     }

    #     channel.basic_publish(
    #         exchange='',
    #         routing_key=servant,
    #         body=json.dumps(msg)
    #     )
    #     self.log (BaseTrace.TRACE_SYS, "Send MSG [%s][%s]->[%s]"  % ( hdr, data, servant) )
    #     connection.close()

    def log ( self, level, txt ):
        # In case we are not initialized yet which will happen
        # when tracing the base level
        try:
            if level >= self.traceLevel.value():
                print ('%s' % txt )
        except:
            print ( 'EARLY TRACE---- %s' % txt )
        
    def msgFunc ( self, service, callbackFunc ):
        pass
    
    
    def startTicker ( self, interval, callbackFunc, context=None ):
        self.tickerId += 1
        threading.Timer(interval, self._internalTicker, args=[self.tickerId, callbackFunc, interval, context]).start()
        
    def _internalTicker ( self, tid, callbackFunc, interval, context ):
        rc = callbackFunc (context)
        if rc is None:
            interval = interval
        else:
            interval = rc
        if interval > 0:          
            threading.Timer(interval, self._internalTicker, args=[self.tickerId, callbackFunc, interval, context]).start()

    def get_db(self):
        #WORKSPACE = r"C:\Users\no1gy\.openclaw\workspace"
        WORKSPACE = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(WORKSPACE, 'test.db')
        
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute('CREATE TABLE IF NOT EXISTS GARY (id INTEGER PRIMARY KEY AUTOINCREMENT, value REAL)')
        conn.execute('CREATE TABLE IF NOT EXISTS AREA (id INTEGER PRIMARY KEY AUTOINCREMENT, area CHAR(20) UNIQUE, value INTEGER)')
        return conn

    def consume_queue(self):
        self.log (BaseTrace.TRACE_SYS,'QUEUE.....STARTUP')



        self.msgConnection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.log (BaseTrace.TRACE_SYS,'QUEUE.....CONNECTED')
        self.msgChannel = self.msgConnection.channel()
        self.msgChannel.queue_declare(queue=self.servant, durable=True)
    
    
    
        def callback(ch, method, properties, body):

            try:
                data = json.loads(body.decode())
                self.log (BaseTrace.TRACE_SYS, "MSG RECEIVED [%s]" % data )
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                self.log (BaseTrace.TRACE_SYS,'[MQ ERROR] [%s]' % e)
    
    
        self.log (BaseTrace.TRACE_SYS,'QUEUE Waiting for messages on [%s]' % self.servant)
        self.msgChannel.basic_consume(queue=self.servant, on_message_callback=callback)

        self.msgChannel.start_consuming()

    def listen_redis(self):

        self.log (BaseTrace.TRACE_SYS,'[REDIS] LISTEN DATA....')
        for msg in self.nvsPubSub.listen():
            self.log (BaseTrace.TRACE_SYS,'REDIS DATA [%s]' % msg )
            try:
                if msg['type'] == 'psubscribe':
                    continue
                # msg format: {'type': 'pmessage', 'pattern': '...', 'channel': '...', 'data': 'set'}
                channel_name = msg.get('channel', '')
                data = msg.get('data', '')
                # Get current value of GARY_TEST
                current_value = r.get('GARY_TEST')
                self.log (BaseTrace.TRACE_SYS, '[REDIS] GARY_TEST changed: [%s]' % current_value)
                redis_event = {
                    'header': {
                        'source': 'redis',
                        'destination': '',
                        'key': 'GARY_TEST',
                        'time': datetime.now().isoformat()
                    },
                    'payload': float(current_value) if current_value is not None else None
                }
                self.notify_sse(redis_event)
                #self.notify_sse(redis_event)
            except Exception as e:
                self.log (BaseTrace.TRACE_SYS,'[REDIS PSUB ERROR] [%s]' % e)
        self.log (BaseTrace.TRACE_SYS, '[REDIS] LISTEN DATA....EXIT')







    class Handler(BaseHTTPRequestHandler):
        # the prefix with 'r' means treat \ not as an escape...raw string
        #WORKSPACE = r"C:\Users\no1gy\.openclaw\workspace\MyApps"
        WORKSPACE = os.path.dirname(os.path.abspath(__file__))

        DB_PATH = os.path.join(WORKSPACE, 'test.db')

        

        last_received = {'id': None, 'value': None, 'time': None}
        
        
        
        
        def do_GET(self): #Runs if GET request
        
            # Get context to the master BaseApp
            master = self.server.master
            master.log (88, "HttpHandler MASTER[%s]" % master )
            master.log (88, "HttpHandler WORKSPACE[%s]" % self.WORKSPACE )
            
            #test db           
            # Need to open DB in same thread ????
            db = master.get_db()
            cursor = db.execute('SELECT id, value FROM GARY ORDER BY id')
            rows = cursor.fetchall()
            db.close()
            print ("DB TEST NumRows[%s]" % len(rows) )
            
            
            
            if self.path == '/':
                fn = os.path.join(self.WORKSPACE, '', 'index.html')
                print ('[RECV] GET / [%s]' % fn)
                with open(fn, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f.read())
            elif self.path == '/stream':
                print ('[RECV] GET /stream')
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.end_headers()
                # Send initial value
                initial_value = None
                initial_event = {
                    'timestamp': time.strftime("%H:%M:%S"),
                    'value': initial_value if initial_value is not None else "(empty)"
                }
                self.wfile.write(f'data: {json.dumps(initial_event)}\n\n'.encode())
                with sse_lock:
                    sse_clients.append(self)
                # Keep connection alive
                while True:
                    time.sleep(1)
                    
                    
            elif self.path == '/data':
                print('[RECV] GET /data...........................................')
                conn = master.get_db()
                cursor = conn.execute('SELECT id, value FROM GARY ORDER BY id')
                rows = cursor.fetchall()
                cursor2 = conn.execute('SELECT value, COUNT(*) as count FROM GARY GROUP BY value ORDER BY value')
                counts = cursor2.fetchall()
                conn.close()
                idList = []
                valList = []
                countDict = {}
                #num = random.randint (1,50 )
                num = min(len(rows), random.randint(1, 50))


                for i in range(num):
                    row = rows[i]
                    id = row[0]
                    val = row[1]
                    idList.append(id)
                    valList.append(val)
                    key = str(val)
                    if key not in countDict:
                        countDict[key] = 0
                    countDict[key] += 1
                
                data = {'ids': idList, 'values': valList, 'counts': countDict}
                print ( "DATA[%s]" % data )
                print(f'-> rows: {len(rows)}')
                print('[SEND] 200')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            elif self.path == '/areas':
                print('[RECV] GET /areas')
                conn = master.get_db()
                cursor = conn.execute('SELECT area, value FROM AREA')
                rows = cursor.fetchall()
                conn.close()
                data = {'areas': [{'area': r[0], 'value': r[1]} for r in rows]}
                print(f'-> areas: {rows}')
                print('[SEND] 200')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
                    
            else:
                self.send_response(404)
                self.end_headers()
        
        
    
        def do_POST(self): #runs automtically if post request
            if self.path == '/submit':
                print ('[RECV] POST /submit')
                length = int(self.headers.get('Content-Length', 0))
                data = json.loads(self.rfile.read(length).decode())
                value = data.get('value')
                print ( ' POST VAL[%s]' % value)
                

            else:
                self.send_response(404)
                self.end_headers()
    
        def log_message(self, format, *args):
            pass
            
    def webNotifySSE(self, payload):
        with sse_lock:
            dead = []
            msg = f'data: {json.dumps(payload)}\n\n'.encode()
            for client in sse_clients:
                self.log (BaseTrace.TRACE_SYS,'WebNotify [%s]->[%s]' % ( msg, client ) )
                try:
                    client.wfile.write(msg)
                except:
                    dead.append(client)
            for c in dead:
                sse_clients.remove(c)

        
    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

 



