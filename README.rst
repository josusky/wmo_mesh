
Status: working.


==================================================
Minimal Demonstration of Mesh network over Pub/Sub
==================================================

Inform peers who subscribe to data made available in a well understood
common tree. Peers download data announced by others, and re-announce 
in turn for their subscribers.

What is the Mesh?  

* A reasonable subset of peers may operate brokers to publish and subscribe to each other.  

* when a peer announces a message, it looks for the file in its tree.
  If it is there, it compares the checksum to the one announced.

* each one downloads data it does not already have (different checksums)
  from peer brokers, and announces those downloads locally for other peers.

As long as there is at least one transitive path between all peers, 
all peers will get all data.

This demonstration is done with MQTT protocol which is more
interoperable than the more robust AMQP protocol. It is intended
to demonstrate the algorithm and the method, not for production use.


.. contents::


Message Format
==============

The message format used is a minimal subset with the same semantics
as the one in use for a few years in `Sarracenia <https://github.com/MetPX/sarracenia>`_
The main change being a switch from AMQP-specific packing, to a
protocol agnostic JSON encoding described here

https://github.com/MetPX/sarracenia/blob/master/doc/sr_postv3.7.rst

Entire format is human readable::

   {  "pubTime" : "20190120T045018.314854383", 
      "baseUrl" : "https://localhost/data", 
      "relPath" : "20190120/WIS/CA/CMC/UpperAir/04/UANT01_CWAO_200445___15103.txt", 
      "size": "TBD",
      "integrity": { "method": "MD5", "value": "d41d8cd98f00b204e9800998ecf8427e" },
      "content": { "encoding": "utf-8", "value": "encoded bytes from the file" }
   }

Boiling it down to this relatively small example makes discussion easier.

*  The *datestamp* marks when the file was posted on the first broker in the network.
   This allows easy calculation of propagation delay across any number of nodes.
   The date format looks like a floating point number,  but is the conventional 
   YYYYMMDDHHMMSS (in UTC timezone) followed by a fraction of a second after the 
   decimal place.  

   This is chosen rather than any sort of epochal second count for readability
   and to avoid worrying about leap seconds. This format is essentially ISO8601 
   basic notation. The standard recommends a *T* be placed between date and time, 
   and there is no convention to use a decimal marker for seconds. The use of a 
   decimal marker allows for different users to give different levels of 
   precision (milliseconds, microseconds, etc...) without ambiguity.

   In ISO8601 when times do not include a timezone marker, it is assumed to be local.
   In the meteorological domain, UTC is more natural. Leaving the Z out seems reasonable.

   The date stamp is critical for subscribers to prevent message loss by knowing
   their lag (how far behind the publisher they are.) 

*  The *baseUrl* marks the static starting point to build the complete download URL.
   It represents the root of the download tree on the remote web server.

   Specifying the baseUrl in each message provides a number of benefits:

   - enables third party transfer, where the broker announcing data doesn't necessarily
     have it locally, it might just know of a remote location, and not be interested in
     it for itself, but it could tell clients where to get it if they want it.

     Reduces load on broker, by having other nodes do the actual transfers.

   - allows many sources of data to be mixed in the same download stream.

   The baseUrl field is replaced when re-publishing downloaded data.


*  the *relPath* is the rest of the download url.

   - isolates the relative path as the basis of comparison for duplicates.
 
   Stays the same with republishing.


*  The last argument is the *headers* of which there can be quite a number.
   In this minimal example, only the *sum* headers is included, giving the
   checksum of the file posted.  The first letter of the sum field designates
   a known checksum algorithm (d = MD5, s=SHA512, n=MD5 of the file name, rather than content)
   Multiple choices for checksum algorithms are offered because some data type
   may have equivalent but not binary identical representations.

   For use cases where full mirroring is desired, additional headers indicating
   permission modes, modification times, etc. may be included.

   The actual checksum of the data downloaded must be compared with the
   advertised one to identify issues. One should always publish with the checksum
   that matches what was downloaded, rather than what was advertised, to avoid loops.

By exchanging messages using only those four fields, a full mesh for the WMO can be implemented.

Audience
========

This demonstration is based on the availability of multiple Linux servers, running
a recent version of Debian or Ubuntu Linux. All of the interactions are command line,
and so familiarity with Linux system administration, editing of configuration files,
etc. is needed.


Peer Setup
==========


Obtain a Server:
----------------

  - for example, a raspberry pi.

    - install base Raspbian from img ( 2018-11-13-raspbian-stretch-lite.img )

    # raspi-config

      - expand file system 
 
      - pick keyboard layout (En US)

    - reboot

  - do network settings.

  - update hostlist for actual addresses. 

Any server running Debian stretch is equivalent. Ubuntu 18.04 is fine also.
Installation instructions will vary by distribution. 


Things to install on Debian:

- sudo apt install git vim python3-xattr python3-pip mosquitto webfs

- sudo apt install python3-paho-mqtt  # available on ubuntu >18.04, but not in Debian stretch

- use pip3 for what you cannot find in repositories::

   # pip3 install paho-mqtt
   Collecting paho-mqtt
     Downloading https://www.piwheels.org/simple/paho-mqtt/paho_mqtt-1.4.0-py3-none-any.whl (48kB)
       100% |████████████████████████████████| 51kB 191kB/s 
   Installing collected packages: paho-mqtt
   Successfully installed paho-mqtt-1.4.0
   root@meshC:/home/pi# 

- get the demo::

    (as an ordinary user, *root* not needed.)
    # git clone https://github.com/MetPX/wmo_mesh
    # cd wmo_mesh
    # mkdir data


Configure a Message Broker
--------------------------

A message broker of some kind needs to be configured.
The demonstration only works with MQTT brokers.  One needs 
to define at least two users:

  - one subscriber (guest), able to read from xpublic/#
  - one publisher (owner), able to post to xpublic/#

Demo was done with an `EMQX <emqtt.io>`_ on a laptop, and the `mosquitto <https://mosquitto.org/>`_ running
on three raspberry pi's.  

Configure Mosquitto
~~~~~~~~~~~~~~~~~~~

Mosquitto by default comes set for memory-constrained devices with lossy flows, where 
lost messages are quickly replaced, and queues simply use memory and are only to support a few 
seconds (100 messages) of backlog. For the WMO mesh application, we want much more asynchrony 
in the message flows, and the systems in question have much more memory, so we need to increase 
the amount of queueing the broker does.

In homage to the WMO-386, maximum message size is set to 500000 bytes (down from 500 MB), this
should not be a practical issue as no file data is sent through these messages.

sudo editor /etc/mosquitto/conf.d/mesh.conf

Add::

        password_file /etc/mosquitto/pwfile
        max_inflight_messages 1000
        max_queued_messages 1000000
        message_size_limit 500000
        upgrade_outgoing_qos True

Then run::

       # sudo touch /etc/mosquitto/pwfile
       # sudo mosquitto_passwd -b /etc/mosquitto/pwfile owner ownerpw
       # sudo mosquitto_passwd -b /etc/mosquitto/pwfile guest guestpw
       # systemctl restart mosquitto
       # systemctl status mosquitto

A server can identify when a client is not processing quickly enough by looking 
in the log (tail /var/log/mosquitto/mosquitto.log )::

   1548600001: New client connected from 172.25.5.170 as 30d4c97c-005a-4e32-a32a-a8765e33483f (c1, k60, u'owner').
   1548600909: Outgoing messages are being dropped for client AWZZ.
   1548601169: Saving in-memory database to /var/lib/mosquitto/mosquitto.db.

Note::
  to convert epochal time stamp in mosquitto.log:
  
  blacklab% TZ=GMT0 date -d '@1548601169'
  Sun Jan 27 14:59:29 GMT 2019
  blacklab%

The above shows the slower, 1st gen raspberry pi is unable to keep up with the message flow
using only single peer. With Sarracenia, one would add *instances* here to have multiple
workers to solve this problem. The limitation is not the demonstration, but rather
MQTT itself, which doesn't permit multiple workers to consume from the same queue
as AMQP does.  However we can add a subscription to a second peer to double the amount
of downloading the slow pi does, and it helps quite a bit.



Configure EMQX
~~~~~~~~~~~~~~~

(from David Podeur...)::

  here are the installation steps for EMQX on
  > Ubuntu 18.04
  > 
  > wget http://emqtt.io/downloads/latest/ubuntu18_04-deb -O emqx-ubuntu18.04-v3.0.0_amd64.deb
  > 
  > sudo dpkg -i emqx-ubuntu18.04-v3.0.0_amd64.deb
  > sudo systemctl enable emqx
  > sudo systemctl start emqx
  > 
  > URL: http://host:18083
  > Username: admin
  > Password: public

Use browser to access management GUI on host:18083

Add users, guest and owner, and set their passwords.
Add the following to /etc/emqx/acl.conf::

 {allow, all, subscribe, [ "xpublic/#" ] }.

 {allow, {user, "owner"}, publish, [ "xpublic/#" ] }.

To have ACL´s take effect, restart::

  systemctl restart emqx

EQMX seems to come by default with sufficient queueing & 
buffering not to lose messages in the tests.

Configure VerneMQ
~~~~~~~~~~~~~~~~~

Download the appropriate vernemq package, and install it.
Create guest and admin users, and set their passwords::

  # vmq-passwd -c /etc/vernemq/vmq.passwd guest
  # vmq-passwd /etc/vernemq/vmq.passwd admin

The Access Control lists would be more complex in practice.
This is a very simple choice for the demo.  Add ACL's needed::

  # cat /etc/vernemq/vmq.acl
  user admin
  topic write xpublic/#
  user guest
  topic read xpublic/#
  #

restart VerneMQ::

  # systemctl restart vernemq 



Start Each Peer
---------------

Each node in the network needs to run:

- a web server to allow others to download.
- a broker to allow messages to flow
- the mesh_peer script to obtain data from peers.

Start Web Servers
~~~~~~~~~~~~~~~~~~

Need to run a web server that exposes folders under the wmo_mesh directory in a very plain way::

    # in one shell start:
    # cd wmo_mesh
    # webfsd -p 8000

An alternative to *webfsd* is the *./trivialserver.py* included in the demo.
It uses more cpu, but is sufficient for a demonstration.

Start mesh_peer.py
~~~~~~~~~~~~~~~~~~
    
In a shell window on start::

   # ./mesh_peer.py --verbose=2 --broker mqtt://guest:guestpw@peer_to_subscribe_to --post_broker mqtt://owner:ownerpw@this_host 

It will download data under the *data/* sub-directory, and publish it on this_host's broker. 

Test
~~~~

On any peer::

   # echo "hello" >data/hello.txt
   # ./mesh_pub.py --post_broker mqtt://owner:ownerpw@this_host data/hello.txt

And the file should rapidly propagate to the peers.  Use *--inline* option to have the file content
include in the message itself (as long as it is below the threshold maximum size.)

For example, with four nodes named blacklab, awzz, bwqd, and cwnp. 
Examples::
 
   blacklab% ./mesh_peer.py --inline --broker mqtt://guest:guestpw@blacklab  --post_broker http://owner:ownerpw@awzz
   pi@BWQD:~/wmo_mesh $ ./mesh_peer.py --inline --broker mqtt://guest:guestpw@blacklab --post_broker mqtt://owner:ownerpw@bwqd
   pi@cwnp:~/wmo_mesh $ ./mesh_peer.py --inline --broker mqtt://guest:guestpw@bwqd --post_broker mqtt://owner:ownerpw@cwnp
   pi@AWZZ:~/wmo_mesh $ ./mesh_peer.py --broker mqtt://guest:guestpw@cwnp --post_broker mqtt://owner:ownerpw@awzz

Any peer can consume messages whether the data is inlined or not.




cleanup
~~~~~~~

A sample cron job for directory cleanup has been included.  It is called as follows::

    ./old_hour_dirs.py 13 data

To remove all directories with UTC date stamps more than 13 hours old.
Sample crontab entry::

    21 * * * * /home/peter/wmo_mesh/old_hour_dirs.py 12 /home/peter/wmo_mesh/data

At 21 minutes past the hour, every hour delete directory trees under /home/peter/wmo_mesh/data which
are more than two hours old.


Insert Some Data
----------------

There are some Canadian data pumps publishing Sarracenia v02 messages over AMQP 0.9 protocol
(RabbitMQ broker) available on the internet. There are various ways of injecting data
into such a network, using the exp_2mqtt for a Sarracenia subscriber.

The WMO_Sketch_2mqtt.conf file is a Sarracenia subscribe that subscribes to messages from
here:

   https://hpfx.collab.science.gc.ca/~pas037/WMO_Sketch/

Which is an experimental data mart sandbox for use in trialling directory tree structures.
It contains an initial tree proposal. The data in the tree is an exposition of a UNIDATA-LDM
feed used as a quasi-public academic feed for North American universities training meteorologists.
It provides a good facsimile of what a WMO data exchange might look like, in terms of volume
and formats. Certain voluminous data sets have been elided from the feed, to ease
experimentation.

1. `Install Sarracenia <https://github.com/MetPX/sarracenia/blob/master/doc/Install.rst>`_

2. Ensure configuration directories are present::

      mkdir ~/.config ~/.config/sarra ~/.config/sarra/subscribe ~/.config/sarra/plugins
      # add credentials to access AMQP pumps.
      echo "amqps://anonymous:anonymous@hpfx.collab.science.gc.ca" >~/.config/sarra/credentials.conf
      echo "amqps://anonymous:anonymous@dd.weather.gc.ca" >>~/.config/sarra/credentials.conf
 
2. Copy configurations present only in git repo, and no released version

   sr_subscribe add WMO_Sketch_2mqtt.conf

   ETCTS201902 changed the format, so need an updated plugin not available in release version::

     cd ~/.config/sarra/plugins
     wget https://raw.githubusercontent.com/MetPX/sarracenia/ETCTS201902/sarra/plugins/exp_2mqtt.py

   which will produce the format required by this demo after the meeting in question. 
    

   What is in the WMO_Sketch_2mqtt.conf file?::

    broker amqps://anonymous@hpfx.collab.science.gc.ca   <-- connect to this broker as anonymous user.
    exchange xs_pas037_wmosketch_public                  <-- to this exchange (root topic in MQTT parlance)
    no_download                                          <-- only get messages, data download will by done
                                                             by mesh_peer.py
    exp_2mqtt_post_broker mqtt://tsource@localhost       <-- tell plugin the MQTT broker to post to.
    post_exchange xpublic                                <-- tell root of the topic tree to post to.
    plugin exp_2mqtt                                     <-- plugin that connects to MQTT instead of AMQP
    subtopic #                                           <-- server-side wildcard to say we are interested in everything.
    accept .*                                            <-- client-side wildcard, selects everything.
    report_back False                                    <-- do not return telemetry to source.


3. Start up the configuration.

   For an initial check, do a first start up of the message transfer client::

       sr_subscribe foreground WMO_Sketch_2mqtt.conf

   After running for a few seconds, hit ^C to abort. Then start it again in daemon mode::

       sr_subscribe start WMO_Sketch_2mqtt.conf

   and it should be running. Logs will be in ~/.config/sarra/log

   Sample output::

       blacklab% sr_subscribe foreground WMO_Sketch_2mqtt.conf  
       2019-01-22 19:43:46,457 [INFO] sr_subscribe WMO_Sketch_2mqtt start
       2019-01-22 19:43:46,457 [INFO] log settings start for sr_subscribe (version: 2.19.01b1):
       2019-01-22 19:43:46,458 [INFO] 	inflight=.tmp events=create|delete|link|modify use_pika=False topic_prefix=v02.post
       2019-01-22 19:43:46,458 [INFO] 	suppress_duplicates=False basis=path retry_mode=True retry_ttl=300000ms
       2019-01-22 19:43:46,458 [INFO] 	expire=300000ms reset=False message_ttl=None prefetch=25 accept_unmatch=False delete=False
       2019-01-22 19:43:46,458 [INFO] 	heartbeat=300 sanity_log_dead=450 default_mode=000 default_mode_dir=775 default_mode_log=600 discard=False durable=True
       2019-01-22 19:43:46,458 [INFO] 	preserve_mode=True preserve_time=True realpath_post=False base_dir=None follow_symlinks=False
       2019-01-22 19:43:46,458 [INFO] 	mirror=False flatten=/ realpath_post=False strip=0 base_dir=None report_back=False
       2019-01-22 19:43:46,458 [INFO] 	Plugins configured:
       2019-01-22 19:43:46,458 [INFO] 		do_download: 
       2019-01-22 19:43:46,458 [INFO] 		do_get     : 
       2019-01-22 19:43:46,458 [INFO] 		on_message: EXP_2MQTT 
       2019-01-22 19:43:46,458 [INFO] 		on_part: 
       2019-01-22 19:43:46,458 [INFO] 		on_file: File_Log 
       2019-01-22 19:43:46,458 [INFO] 		on_post: Post_Log 
       2019-01-22 19:43:46,458 [INFO] 		on_heartbeat: Hb_Log Hb_Memory Hb_Pulse RETRY 
       2019-01-22 19:43:46,458 [INFO] 		on_report: 
       2019-01-22 19:43:46,458 [INFO] 		on_start: EXP_2MQTT 
       2019-01-22 19:43:46,458 [INFO] 		on_stop: 
       2019-01-22 19:43:46,458 [INFO] log_settings end.
       2019-01-22 19:43:46,459 [INFO] sr_subscribe run
       2019-01-22 19:43:46,459 [INFO] AMQP  broker(hpfx.collab.science.gc.ca) user(anonymous) vhost()
       2019-01-22 19:43:46,620 [INFO] Binding queue q_anonymous.sr_subscribe.WMO_Sketch_2mqtt.24347425.16565869 with key v02.post.# from exchange xs_pas037_wmosketch_public on broker amqps://anonymous@hpfx.collab.science.gc.ca
       2019-01-22 19:43:46,686 [INFO] reading from to anonymous@hpfx.collab.science.gc.ca, exchange: xs_pas037_wmosketch_public
       2019-01-22 19:43:46,687 [INFO] report_back suppressed
       2019-01-22 19:43:46,687 [INFO] sr_retry on_heartbeat
       2019-01-22 19:43:46,688 [INFO] No retry in list
       2019-01-22 19:43:46,688 [INFO] sr_retry on_heartbeat elapse 0.001044
       2019-01-22 19:43:46,689 [ERROR] exp_2mqtt: authenticating as tsource 
       2019-01-22 19:43:48,101 [INFO] exp_2mqtt publising topic=xpublic/v03/post/2019012300/KWNB/SX, body=["20190123004338.097888", "https://hpfx.collab.science.gc.ca/~pas037/WMO_Sketch/", "/2019012300/KWNB/SX/SXUS22_KWNB_230000_RRX_e12080ee6aaf254ab0cd97069be3812b.txt", {"parts": "1,278,1,0,0", "atime": "20190123004338.0927228928", "mtime": "20190123004338.0927228928", "source": "UCAR-UNIDATA", "from_cluster": "DDSR.CMC,DDI.CMC,DDSR.SCIENCE,DDI.SCIENCE", "to_clusters": "DDI.CMC,DDSR.CMC,DDI.SCIENCE,DDI.SCIENCE", "sum": "d,e12080ee6aaf254ab0cd97069be3812b", "mode": "664"}]
       2019-01-22 19:43:48,119 [INFO] exp_2mqtt publising topic=xpublic/v03/post/2019012300/KOUN/US, body=["20190123004338.492952", "https://hpfx.collab.science.gc.ca/~pas037/WMO_Sketch/", "/2019012300/KOUN/US/USUS44_KOUN_230000_4d4e58041d682ad6fe59ca9410bb85f4.txt", {"parts": "1,355,1,0,0", "atime": "20190123004338.488722801", "mtime": "20190123004338.488722801", "source": "UCAR-UNIDATA", "from_cluster": "DDSR.CMC,DDI.CMC,DDSR.SCIENCE,DDI.SCIENCE", "to_clusters": "DDI.CMC,DDSR.CMC,DDI.SCIENCE,DDI.SCIENCE", "sum": "d,4d4e58041d682ad6fe59ca9410bb85f4", "mode": "664"}]
       2019-01-22 19:43:48,136 [INFO] exp_2mqtt publising topic=xpublic/v03/post/2019012300/KWNB/SM, body=["20190123004338.052487", "https://hpfx.collab.science.gc.ca/~pas037/WMO_Sketch/", "/2019012300/KWNB/SM/SMVD15_KWNB_230000_RRM_630547d96cf1a4f530bd2908d7bfe237.txt", {"parts": "1,2672,1,0,0", "atime": "20190123004338.048722744", "mtime": "20190123004338.048722744", "source": "UCAR-UNIDATA", "from_cluster": "DDSR.CMC,DDI.CMC,DDSR.SCIENCE,DDI.SCIENCE", "to_clusters": "DDI.CMC,DDSR.CMC,DDI.SCIENCE,DDI.SCIENCE", "sum": "d,630547d96cf1a4f530bd2908d7bfe237", "mode": "664"}]
       2019-01-22 19:43:48,152 [INFO] exp_2mqtt publising topic=xpublic/v03/post/2019012300/KWNB/SO, body=["20190123004338.390638", "https://hpfx.collab.science.gc.ca/~pas037/WMO_Sketch/", "/2019012300/KWNB/SO/SOVD83_KWNB_230000_RRX_8e94b094507a318bc32a0407a96f37a4.txt", {"parts": "1,107,1,0,0", "atime": "20190123004338.388722897", "mtime": "20190123004338.388722897", "source": "UCAR-UNIDATA", "from_cluster": "DDSR.CMC,DDI.CMC,DDSR.SCIENCE,DDI.SCIENCE", "to_clusters": "DDI.CMC,DDSR.CMC,DDI.SCIENCE,DDI.SCIENCE", "sum": "d,8e94b094507a318bc32a0407a96f37a4", "mode": "664"}]
       2019-01-22 19:43:48,170 [INFO] exp_2mqtt publising topic=xpublic/v03/post/2019012300/EGRR/IU, body=["20190123004331.855253", "https://hpfx.collab.science.gc.ca/~pas037/WMO_Sketch/", "/2019012300/EGRR/IU/IUAA01_EGRR_230042_99240486f422b0cb2dcead7819ba8100.bufr", {"parts": "1,249,1,0,0", "atime": "20190123004331.852722168", "mtime": "20190123004331.852722168", "source": "UCAR-UNIDATA", "from_cluster": "DDSR.CMC,DDI.CMC,DDSR.SCIENCE,DDI.SCIENCE", "to_clusters": "DDI.CMC,DDSR.CMC,DDI.SCIENCE,DDI.SCIENCE", "sum": "d,99240486f422b0cb2dcead7819ba8100", "mode": "664"}]
       2019-01-22 19:43:48,188 [INFO] exp_2mqtt publising topic=xpublic/v03/post/2019012300/CWAO/FT, body=["20190123004337.955676", "https://hpfx.collab.science.gc.ca/~pas037/WMO_Sketch/", "/2019012300/CWAO/FT/FTCN31_CWAO_230000_AAA_81bdc927f5545484c32fb93d43dcf3ca.txt", {"parts": "1,182,1,0,0", "atime": "20190123004337.952722788", "mtime": "20190123004337.952722788", "source": "UCAR-UNIDATA", "from_cluster": "DDSR.CMC,DDI.CMC,DDSR.SCIENCE,DDI.SCIENCE", "to_clusters": "DDI.CMC,DDSR.CMC,DDI.SCIENCE,DDI.SCIENCE", "sum": "d,81bdc927f5545484c32fb93d43dcf3ca", "mode": "664"}]
    
As these messages come from Sarracenia, they include a lot more fields. There is also a feed from 
the current Canadian datamart which has a more eclectic mix of data, but not much in WMO formats:

        https://raw.githubusercontent.com/MetPX/sarracenia/master/sarra/examples/subscribe/dd_2mqtt.conf

There will be imagery and Canadian XML files and in a completely different directory tree that is much more difficult
to clean.

Note that the *source* field is set, in this feed, to *UCAR-UNIDATA*, which is the local name in ECCC
for this data source. One would expect the CCCC of the centre injecting the data to be provided in this field.


Observations
============

Does it work?
-------------

Hard to tell. If you set up passwordless ssh between the nodes, you can generate some gross level reports like so::

      blacklab% for i in blacklab awzz bwqd cwnp; do ssh $i du -sh wmo_mesh/data/*| awk ' { printf "%10s %5s %s\n", "'$i'", $1, $2 ; };' ; done | sort -r -k 3
          cwnp   31M wmo_mesh/data/2019012419
          bwqd   29M wmo_mesh/data/2019012419
      blacklab   29M wmo_mesh/data/2019012419
          awzz   29M wmo_mesh/data/2019012419
          cwnp   29M wmo_mesh/data/2019012418
          bwqd   28M wmo_mesh/data/2019012418
      blacklab   28M wmo_mesh/data/2019012418
          awzz   28M wmo_mesh/data/2019012418
          cwnp   32M wmo_mesh/data/2019012417
          bwqd   32M wmo_mesh/data/2019012417
      blacklab   31M wmo_mesh/data/2019012417
          awzz   32M wmo_mesh/data/2019012417
      blacklab%

So, not perfect. Why? Message loss occurs when subscribers fall too far behind publishers.

Sample Outputs
--------------

Below are some sample outputs of mesh_peer.py running. A message received on node *CWNP*,
served by node *blacklab* , but *CWNP* already has it, so it is not downloaded::

    topic:  xpublic/v03/post/2019013003/GTS/CWAO/SX
    payload:  ['20190130033826.740083', 'http://blacklab:8000/data', '/2019013003/GTS/CWAO/SX/SXCN19_CWAO_300300_ac8d831ec7ffe25b3a0bbc3b22fca2c4.txt', { 'sum': 'd,ac8d831ec7ffe25b3a0bbc3b22fca2c4' }]
        lag: 42.4236   (mean lag of all messages: 43.8661 )
    file exists: data/2019013003/GTS/CWAO/SX/SXCN19_CWAO_300300_ac8d831ec7ffe25b3a0bbc3b22fca2c4.txt. Should we download? 
    retrieving sum
    hash: d,ac8d831ec7ffe25b3a0bbc3b22fca2c4
    same content:  data/2019013003/GTS/CWAO/SX/SXCN19_CWAO_300300_ac8d831ec7ffe25b3a0bbc3b22fca2c4.txt
 
In this case, the consumer is receiving a message 42 seconds after it's initial 
injection into the network. Below is a case where blacklab has a file 
that *CWNP* wants::

    topic:  xpublic/v03/post/2019013003/GTS/AMMC/FT
    payload: ['20190130033822.951880', 'http://blacklab:8000/data', '/2019013003/GTS/AMMC/FT/FTAU31_AMMC_292300_AAC_c267e44d8cfc52af0bbc425c46738ad7.txt', { 'sum': 'd,c267e44d8cfc52af0bbc425c46738ad7' }]
    lag: 33.924   (mean lag of all messages: 43.8674 )
    writing attempt 0: data/2019013003/GTS/AMMC/FT/FTAU31_AMMC_292300_AAC_c267e44d8cfc52af0bbc425c46738ad7.txt
    calculating sum
    published: t=xpublic/v03/post/2019013003/GTS/AMMC/FT, body=[ "20190130033822.951880", "http://cwnp:8000/data", "/2019013003/GTS/AMMC/FT/FTAU31_AMMC_292300_AAC_c267e44d8cfc52af0bbc425c46738ad7.txt", { "sum": "d,c267e44d8cfc52af0bbc425c46738ad7" }]
 
The file is downloaded and written to the local path, checksum of the 
downloaded data determined, and then an updated message published, with the 
base URL changed to refer to the local node *CWNP* (the checksum is the same
as in the input message because it was correct.)

Determinining Subscriptions
---------------------------

In the sample output above, there is a line listing **lag** (the age of the message
being ingested, based on it's timestamp.) Lag of individual messages can be 
highly variable due to the effects of queueing. If lag is consistently too high,
or an increasing trend is identified over time, one must address it, as eventually
the consumer will fall too far behind the source and the source will begin dropping
messages.

It is here were a major practical difference between AMQP and MQTT is obvious. To
increase the number of messages being consumer per unit time with AMQP, one would add
consumers to a shared queue. With Sarracenia, this means increasing the *instances* setting.
Generally increasing instances provides enough performance.

With MQTT, on the other hand, multiple consumers to a single queue is not possible, so
one must partition the topic space using subtopic filtering.  The first simple subscription is:: 

   # ./mesh_peer.py --verbose=2 --broker mqtt://guest:guestpw@peer_to_subscribe_to --post_broker mqtt://owner:ownerpw@this_host 

If that is too slow, then the same subscription must be tuned For example::

   # ./mesh_peer.py --subtopic '+/GTS/+/IU/#' --subtopic '+/GTS/+/IS/#'--verbose=2 --broker mqtt://guest:guestpw@peer_to_subscribe_to --post_broker mqtt://owner:ownerpw@this_host  --clean_session

would only subscribe to BUFR reports on the peer, from all over the world.  
Whenever you change the --subtopic settings, you should use the --clean_session setting, 
as by default mesh_peer.py will try to connect to recover any messages missed while it was stopped.
Once you have finished tuning, remove the --clean_session from the options to avoid
data loss.

Another means of dividing the flow, one could subscribe to reports on the peer from 
different origin codes::

   # ./mesh_peer.py --subtopic '+/GTS/KWNB/+/#' --subtopic '+/GTS/KWBC/+/#'--verbose=2 --broker mqtt://guest:guestpw@peer_to_subscribe_to --post_broker mqtt://owner:ownerpw@this_host 

Ensure that the combination of all subscriptions includes all of the data 
of to be downloaded from the peer. In order to ensure that data flows in
the event of the failure of any one peer, each node should maintain equivalent
subscriptions to at least two nodes in the network.  

Some future work would be to create a second daemon, mesh_dispatch, that would
automatically spawn mesh_peer instances with appropriately partitioned subscriptions.
It should be straightforward, but there wasn´t time before the meeting.


Easy Parallellism
~~~~~~~~~~~~~~~~~

There is a script called mesh_multi.sh which takes three arguments:

 * node - name of the remote node to subscribe to.

 * broker - the remote node's broker url.

 * workers - the number of worker processes to launch.

The script is only a few lines and it launches a single *dispatcher* configuration 
of the mesh_peer, as well the N workers. The dispatcher downloads nothing, it only subscribes
to the messages on the remote broker, and then distributes them to a separate download topic tree
for each worker. The workers then each download 1/N of the files announced.

so to implement one node of the wmo_mesh, start up this script with two 
different nodes::

  ./mesh_multi.sh cwao mqtt://cwao.cmc.ec.gc.ca  5
  ./mesh_multi.sh kwbc mqtt://kwbc.nws.noaa.gov  5

Each one will start a log for each worker and the dispatcher. Here
are the log files created for subscription bwqd node with five workers::

  blacklab% ls mesh*bwqd*.log
  mesh_dispatch_bwqd.log  mesh_worker_00_bwqd.log  mesh_worker_01_bwqd.log  mesh_worker_02_bwqd.log  mesh_worker_03_bwqd.log  mesh_worker_04_bwqd.log
  blacklab% 




Bandwidth
---------

It should be noted that if each node is subscribed to at least two peers, 
each announcement will be read from two sources and sent to two subscribers 
(minimum four traversals), and the data itself will be read once, and likely
delivered to one subscriber. The multiple extra sends of announcements 
is one point against including the data itself in the message stream.

where peering to any node may have similar cost. One can adapt to different
topologies (such as, where it is advantageous to have peers within one region)
by careful selection of peering. No change in design is needed.


Compared to Current GTS: More Even Distribution of Uplink
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The *Regional Main Data Communications Network* (RMDCN), an MPLS network
(Multi-protocol Lan Service, a technology that results in a central 
node to interconnect subscribers, or a star-topology) network, that 
the European Centre for Medium-range Weather Forecasting (ECMWF) has 
contracted, is the de-facto standard physical link over which the GTS links
are transported. In this network, there is little to no advantage (lower 
latency of higher bandwidth) to peering with geopraphic proximity.

However, links in such networks are typically symmetric: They have
the same bandwidth available for both sending and receiving data. As the data 
for any one country is much less to send than the data from the rest of the
world to be received, each country will have excess unused sending capacity
on their RMDCN link. The exception to this would be GTS regional 
telecomunications hubs (RTH), which may need to obtain higher capacity
RMDCN conncetions in order to send upto the whole world´s data to each of it´s 
client NC´s. 

In comparison to this current layering of point to point GTS links over the 
RMDCN, the mesh exchange proposal would reduce to the RTH need for uplink 
bandwidth, and increase the reliance on existing likely unused uplink 
bandwidth at the other centres, potentially lowering the cost of RMDCN as a whole.
The GTS is currently very limited in it´s volume, so the effect would be 
negligeable, but if volumes expand, this inherently more even spread of 
uplink bandwidth could become more noticeable. 



Open to Future Changes via URL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While transport is a solved problem, this approach in no way limits
future adoption of new technology, by dint of supporting additional
protocols for downloading (e.g. ipfs) that may result in more efficient
use of available bandwidth.




Known Demo Limitations 
======================

* **Retrieval is http or https only** not SFTP, or ftp, or ftps. (Sarracenia does all of them.)

* **The same tree everywhere.** Sarracenia has extensive support for transforming the tree on the fly.
  Not everyone will be happy with any tree that is specified, being able to transform the tree
  makes adoption easier for usage apart from WMO nodes.

* **No broker management.** Sarracenia incorporates user permissions management of a RabbitMQ broker,
  so the broker can be entirely managed, after initial setup, with the application. It implements
  a flexible permission scheme that is onerous to do manually.
  In the demo, access permissions must be done manually. 

* **credentials in command-line** better practice to put them in a separate file, as Sarracenia does.

* **logging**, in Sarracenia, logs are available for the dozens of daemons running in a real deployment.
  They are rotated daily, and retention is configurable.  The demo writes to standard output and error streams.
  The logs also provide timestamps in the timezone preferred. 

* mesh_peer is in **entirely in python** in this demo, which is relatively resource intensive and 
  will not obtain optimal performance. Sarracenia, for example, allows for optimized plugins to 
  replace python processing where appropriate. On the other hand, a raspberry pi is very constrained
  and keeping up with an impressive flow with little apparent load. 

* demo **reads every file twice**, once to download, once to checksum. Checksum is then cached
  in an extended attribute, which makes it non-portable to Windows. Sarracenia usually checksums
  files are they are downloaded (unless an accelerated binary downloader plugin is used.)
  avoiding one read.

* demo **reads every file into memory**. Chunking would be more efficient and is done by 
  Sarracenia.

* *Potential race condition* As there is no file locking, if a file is obtained from two 
  nodes at exactly the same time, the content of a file already transferred may disappear 
  while the second writer is writing it. Unclear if this is a real problem, requires 
  further study.

* Other than observations of lag, the **client cannot determine if messages have been lost.**
  MQTT has limited buffering, and it will discard messages and note the loss on the 
  server log. Client has no way of knowing that there are messages missing.  
  One could add administrative messages to the protocol to warn of such things 
  in a different topic hierarchy using a separate consumer. That hierarchy 
  would have very low traffic. This is not a protocol specific issue. It is 
  fundamental that subscribers must keep up with publishers, or messages
  will be lost.

* Security: **one should validate the baseUrl** is reasonable given the source of the 
  message. This is a variety of *cross-site scripting* that needs to be worried over in
  deployment.

* Security: reviews may complain about **use of MD5**, SHA512 is also available, but the
  correct algorithms to use will need to be maintained over time. This is one aspect
  that needs to be standardized (everyone needs to have a list of well-known checksum
  algorithms.)

* Security: **mqtts, and https needed** in production scenarios.

Background/History
==================

This demonstration code was written to illustrate the main algorithm for multiple peers
to maintain a synchronized directory tree. It was originally envisioned at the
a meeting of the World Meteorological Organization, Committee for Basic Systems
(WMO-CBS) Namibia (2009) as an informal discussion. The idea was a bit too far from
what others were doing to be understood at that point, and so a `Canadian stack <https://github.com/MetPX/sarracenia>`_
fully exploiting the idea was developed to prove the concept to ourselves.
It is very different from traditional global telecommunications system (GTS),
and so members need a more in depth introduction. As people become comfortable 
with it, features can be added to it so that it can function as a reference
implementation for others' stacks.

All of the WMO members have many constraints on software adoption, and so 
proposing a stack for use by others, especially one that is poorly understood, 
would not be a successful endeavour. So rather than propose the Canadian stack
itself, the central algorithm was re-implemented in a pared down way with an emphasis
on ease of communication. *Ease* is a relative term. The audience for which this is *easy*
to understand is a small one, but it includes the people would would create their own 
national implementations. This proposal is for underlying plumbing of data exchange,
and end users are likely not interested in it. End user services would likely use
other software layered over this transport one.

This proposal was first discussed in detail at a meeting of World Meteorological 
Organization's Expert Team on computing and telecommunications systems ( ET-CTS ) 
in Buenos Aires, 2019/02 11-15. There were some changes made to the encoding,
which mostly improved readability, which have been incorporated.  We are now
using the Issue tracker to follow up.

FAQ
===

Priority
--------

Traditional GTS had the concept of higher priority messages. The effect of priorities
in traditional GTS was to set up queues at each priority level. Although it was not
explicitly stated, generally the priority implementation was all the items at a higher
priority would be sent before any at the next level priority were. 

In a pub/sub system, the same effect can be achieved by using subscribers for
high priority messages which are separate from the others. so one would run a mesh_peer.py
subscribed to weather warnings and administrative messages, a second one for observations
and FT's and the like, and then a third one for the balance of data (grib ;-)

Corruption from Download Race Condition 
---------------------------------------

Rarely, if multiple subscribers on the same system get a message from multiple subscribers 
about the same file, and it hasn't been downloaded yet, each one will download and write
it locally.  Will that not result in file corruption?

Implementation must ensure that they do not truncate files when they are opened for writing.
In Linux, some standard methods of performing input output start by truncating the file.
This truncation of file open must be avoided (a matter of careful API use.)  Further, 
in Linux, each process obtains a separate file pointer, and will start writing
at the beginning of the file. If two processes are downloading the same file at once,
they will write the same bytes twice at slightly different times, and no corruption will occur.


Copyright
=========

This work is being done under the aegis of the Meteorological Product Exchanger (MetPX) project.
The MetPX project is copyright Government of Canada, using the same license as the Linux
kernel (GPLv2) and is thus free to use, modify and distribute as long as the changes are 
made public as well. Contributors retain copyright to their contributions.

