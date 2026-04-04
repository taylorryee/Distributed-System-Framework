import argparse
import redis
#Distributed system framework
class dApp(object):
    
    class Parser(argparse.ArgumentParser):
        pass

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--name',type=str,required=True)
        self.args = parser.parse_args()
        self.name = self.args.name
        
        self.callbacks = {}#local store key->callback
        self.parms = {}#local store parms

        startRedis = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)# create Redis client connection to shared server
        startRedis.config_set('notify-keyspace-events', '$K')# enable keyspace notifications for certain key events (e.g., SET on string keys)

        self.redis = startRedis# store Redis client for read/write operations
        self.pubSub = startRedis.pubsub()# create PubSub object for subscribing to and receiving Redis events/messages

        self.redis_listener()#configurers pubsub to listen for key changes and activate handle_redis_event on noti
        self.pubSub.run_in_thread() #listens for key changes in seperate thread
   

    class Parm(object): #Represents one key,value locally 
        def __init__(self,name,value,dAppInstance):
            self.name = name 
            self.value = value 
            self.dAppInstance = dAppInstance


        def update_parm(self):
            updated_val = self.dAppInstance.redis.get(self.name)
            self.value = updated_val
            

    def redis_listener(self):
        self.pubSub.psubscribe(**{"__keyspace@0__:*": self.handle_redis_event})

    def handle_redis_event(self,message):
        key = message["channel"].split(":")[-1]
        if key in self.parms: #We need this check because our redis_listener we setup on intilization listens for all key changes to global redis - 
            #and we only care about key changes that are on keys that exisit in our instance
            for callback in self.callbacks[key]:
                callback()

    def new_parm(self,name,value): 
        redis_check = self.redis.set(name,value,nx=True) #returns True if we set, None if already set
        if not redis_check:
             self.parms[name] = self.Parm(name,self.redis.get(name),self)
             self.callbacks[name] = [self.parms[name].update_parm]
        else:
            self.parms[name] = self.Parm(name,value,self)
            self.callbacks[name] = [self.parms[name].update_parm]
            



    #def update_key(self,key,value):


        
            
    


