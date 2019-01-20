#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import os,json,sys,time,argparse,platform,urllib.parse
from hashlib import md5

host=platform.node()

parser = argparse.ArgumentParser(description='post some files')

parser.add_argument('--post_broker', default='mqtt://' + host, help=" mqtt://user:pw@host - broker to post to" )
parser.add_argument('--post_baseurl', default='http://' + host + ':8000/data', help='base of the tree to publish')
parser.add_argument('--post_base_dir', default= os.getcwd() + '/data', help='local directory corresponding to baseurl')
parser.add_argument('--post_exchange', default='xpublic', help='root of the topic hierarchy (similar to AMQP exchange)')
parser.add_argument('--post_topic_prefix', default='/v03/post', help='means of separating message versions and types.')
parser.add_argument('file', nargs='+', type=argparse.FileType('r'), help='files to post')

args = parser.parse_args( )

post_client = mqtt.Client( protocol=mqtt.MQTTv311 )
pub = urllib.parse.urlparse( args.post_broker) 
if pub.username != None:
    post_client.username_pw_set( pub.username, pub.password )
post_client.connect( pub.hostname )

post_client.loop_start()

for f in args.file:
    os.stat( f.name )
    
    f = open(f.name,'rb')
    d = f.read()
    f.close()
     
    hash = md5()
    hash.update(d)
    
    now=time.time()
    nsec = ('%.9g' % (now%1))[1:]
    datestamp  = time.strftime("%Y%m%d%H%M%S",time.gmtime(now)) + nsec
      
    relpath = os.path.abspath(f.name).replace( args.post_base_dir, '' )
    if relpath[0] == '/':
        relpath= relpath[1:]
    
    p = json.dumps( (datestamp, args.post_baseurl, relpath, { "sum":"d,"+hash.hexdigest() } )) 
    
    if os.path.dirname(relpath) == '/':
        subtopic=''
    else:
        subtopic=os.path.dirname(relpath)

    t = args.post_exchange + args.post_topic_prefix + '/' + subtopic
    
    print( "topic=%s , payload=%s" % ( t, p ) )
    post_client.publish(t, p, qos=2 )
    

post_client.loop_stop()