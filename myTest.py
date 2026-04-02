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
        self.custom_run = None
        self.store = {} #local store

        # startRedis = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        # # create Redis client connection to shared server
        # startRedis.config_set('notify-keyspace-events', '$K')
        # # enable keyspace notifications for certain key events (e.g., SET on string keys)

        # self.redis = startRedis
        # # store Redis client for read/write operations
        # self.redisListener = startRedis.pubsub()
        # # create PubSub object for subscribing to and receiving Redis events/messages

        if self.custom_run:
            self.custom_run()
    
    def set_local(self,key,value):
        if key in self.store:
            self.store[key].append(value)
        else:
            self.store[key] = [value]

        
    def get_local(self,key):
        if key in self.store:
            print(self.store[key])
            return self.store[key]




        
            
    


