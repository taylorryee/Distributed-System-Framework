import argparse
import redis
import time
#Distributed system framework
class dApp(object):
    
    class Parser(argparse.ArgumentParser):
        pass

    class Parm(object): #Represents one key,value locally 
        def __init__(self,name,value,dAppInstance):
            self.name = name 
            self.value = value 
            self.dAppInstance = dAppInstance

        def update_parm_callback(self,key,new_val):
            #print(f"{self.name}'s key:{key} changed from {self.value} to {new_val}")
            self.value = new_val
            

    def __init__(self,name):
        # parser = argparse.ArgumentParser()
        # parser.add_argument('--name',type=str,required=True)
        # self.args = parser.parse_args()
        # self.name = self.args.name
        self.name = name
        self.callbacks = {}#local store key->callback
        self.parms = {}#local store parms

        startRedis = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)# create Redis client connection to shared server
        startRedis.config_set('notify-keyspace-events', '$K')# enable keyspace notifications for certain key events (e.g., SET on string keys)

        self.redis = startRedis# store Redis client for read/write operations
        self.pubSub = startRedis.pubsub()# create PubSub object for subscribing to and receiving Redis events/messages

        self.redis_listener()#configurers pubsub to listen for key changes and activate handle_redis_event on noti
        self.pubSub.run_in_thread() #listens for key changes in seperate thread
   
         
    def redis_listener(self):
        self.pubSub.psubscribe(**{"__keyspace@0__:*": self.handle_redis_event})

    def handle_redis_event(self,message):
        name = message["channel"].split(":")[-1]
        if name in self.parms and name in self.callbacks: #We need this check because our redis_listener we setup on intilization listens for all key changes to global redis - 
            #and we only care about key changes that are on keys that exisit in our instance
            global_val = self.redis.get(name)
            for callback in self.callbacks[name]: #callback functions accept (key,val)
                callback(name,global_val)

    def link_callbacks(self,name,callbacks):
        if name not in self.callbacks:
            self.callbacks[name] = []
        self.callbacks[name].extend(callbacks)

    def log_callback(self,key,val):
        pass
   
    def new_parm(self,name,value):#only create parm if it does not exist in global redis storage
        if name in self.parms:#parm already exists locally
            return 
        redis_check = self.redis.set(name,value,nx=True) #returns True if we set, None if already set
        if not redis_check: #if parm already exists globaly
             global_val = self.redis.get(name)
             self.parms[name] = self.Parm(name,global_val,self)

        else:#if we created new parm
            self.parms[name] = self.Parm(name,value,self)
        time.sleep(1)
        self.link_callbacks(name,[self.parms[name].update_parm_callback,self.log_callback]) #Link callback
    

    def update_parm(self, name, value):
        if name not in self.parms:
            return
        self.redis.set(name, value) #Allow callback to update parm value
    





        
            
    


