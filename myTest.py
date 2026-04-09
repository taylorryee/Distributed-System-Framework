import argparse
import redis
import time
#Distributed system framework
class dApp(object):
    
    class Parser(argparse.ArgumentParser):
        pass

    class Parm(object): #Represents one key,value locally 
        def __init__(self,name,dAppInstance,defVal):
            self.name = name 
            self.value = None
            self.dAppInstance = dAppInstance
            self.dAppInstance.link_callback(name,self.update_parm_callback)

            self.dAppInstance.setRedis(name,defVal,nx=True)
            self.value = self.dAppInstance.getRedis(name)


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
        self.keys = set()



        startRedis = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)# create Redis client connection to shared server
        startRedis.config_set('notify-keyspace-events', '$K')# enable keyspace notifications for certain key events (e.g., SET on string keys)

        self.redis = startRedis# store Redis client for read/write operations
        self.pubSub = startRedis.pubsub()# create PubSub object for subscribing to and receiving Redis events/messages

        # self.redis_listener()#configurers pubsub to listen for key changes and activate handle_redis_event on noti
        self.pubSub.run_in_thread() #listens for key changes in seperate thread
   
    
    def getRedis(self,name):
        return self.redis.get(name)

    def setRedis(self,name,val,nx=False):
        return self.redis.set(name,val,nx=nx)
    
    # def redis_listener(self):
    #     self.pubSub.psubscribe(**{"__keyspace@0__:*": self.handle_redis_event})

    def handle_redis_event(self,message):
        name = message["channel"].split(":")[-1]
        # if name in self.parms and name in self.callbacks: #We need this check because our redis_listener we setup on intilization listens for all key changes to global redis - 
        #     #and we only care about key changes that are on keys that exisit in our instance
        if name not in self.callbacks:
            return
        global_val = self.redis.get(name)
        
        for callback in self.callbacks[name]: #callback functions accept (key,val)
            callback(name,global_val)

    def link_callback(self,name,callback):
        if name not in self.callbacks:
            self.callbacks[name] = []
        self.callbacks[name].append(callback)

        if name not in self.keys:
            pattern = f"__keyspace@0__:{name}"
            self.pubSub.psubscribe(**{pattern: self.handle_redis_event})
            self.keys.add(name)


    def log_callback(self,key,val):
        print(f"{key}'s value changed to {val}")
   
    # def new_parm(self,name,value):#only create parm if it does not exist in global redis storage
    #     if name in self.parms:#parm already exists locally
    #         return 
    #     redis_check = self.redis.set(name,value,nx=True) #returns True if we set, None if already set
    #     if not redis_check: #if parm already exists globaly
    #          global_val = self.redis.get(name)
    #          self.parms[name] = self.Parm(name,global_val,self)

    #     else:#if we created new parm
    #         self.parms[name] = self.Parm(name,value,self)
    #     #time.sleep(1) #Test -> thread timing makes it so that log_callback is called on creation without 
    #     self.link_callback(name,self.parms[name].update_parm_callback)
    #     self.link_callback(name,self.log_callback)
    def parm(self, name, defVal=None):
        if name not in self.parms:
            self.parms[name] = self.Parm(name, self, defVal)
        return self.parms[name]

    def update_parm(self, name, value):
        if name not in self.parms:
            return
        self.redis.set(name, value) #Allow callback to update parm value
    





        
            
    


