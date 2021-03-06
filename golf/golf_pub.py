#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import os,json,sys,time,argparse,platform,urllib.parse
from hashlib import md5

TODOWNLOAD='to_download.pipe'
tdp=open(TODOWNLOAD,'r')

host=platform.node()

rcs = [ "Connection successful", "Connection refused – incorrect protocol version", 
        "Connection refused – invalid client identifier", "Connection refused – server unavailable",
        "Connection refused – bad username or passwor", "Connection refused – not authorised", 
        "unknown error" 
      ]

def pub_connect(client, userdata, flags, rc):
    if not (0 <= rc <=5): rc=6
    print( rcs[rc] )

def pub_publish(client, userdata, mid):
    print("published mid=%s" % ( mid ) )

parser = argparse.ArgumentParser(description='post some files')

parser.add_argument('--post_broker', default='mqtt://' + host, help=" mqtt://user:pw@host - broker to post to" )
parser.add_argument('--post_baseurl', default='http://' + host + ':8000/data', help='base of the tree to publish')
parser.add_argument('--post_base_dir', default= os.getcwd() + '/data', help='local directory corresponding to baseurl')
parser.add_argument('--post_exchange', default='xpublic', help='root of the topic hierarchy (similar to AMQP exchange)')
parser.add_argument('--post_topic_prefix', default='/v03/post', help='means of separating message versions and types.')

args = parser.parse_args( )

post_client = mqtt.Client( protocol=mqtt.MQTTv311 )

post_client.on_connect = pub_connect
post_client.on_publish = pub_publish

pub = urllib.parse.urlparse( args.post_broker) 
if pub.username != None:
    post_client.username_pw_set( pub.username, pub.password )
post_client.connect( pub.hostname )

post_client.loop_start()


for l in tdp:
      
    m=json.loads(l)
    dnld_result=sys.stdin.readline()
    print('message= %s' % m )
    print('result= %s'  % dnld_result )

    continue

    relpath = os.path.abspath(f.name).replace( args.post_base_dir, '' )

    if relpath[0] == '/':
        relpath= relpath[1:]
    
    p = json.dumps( (datestamp, args.post_baseurl, relpath, { "sum":"d,"+h.hexdigest() } )) 
    
    if os.path.dirname(relpath) == '/':
        subtopic=''
    else:
        subtopic=os.path.dirname(relpath)

    t = args.post_exchange + args.post_topic_prefix + '/' + subtopic
    
    print( "topic=%s , payload=%s" % ( t, p ) )
    info = post_client.publish(t, p, qos=1 )
    info.wait_for_publish()
    

post_client.loop_stop()
