#!/usr/bin/python
# -*- coding: utf-8 -*-

import queue
import sys
import time
import threading
import json

import RestToolbox as RestToolbox

## Print help message

if len(sys.argv) != 7:
    print("""
Sample script that continuously monitors the arrival of new DICOM
images into Orthanc (through the Changes API).

Usage: %s [hostname] [HTTP port] [username] [password] [orthanc peer name] [foo url]
For instance: %s 127.0.0.1 8042 foo foo orthanc-bar http://10.8.0.8:8042
""" % (sys.argv[0], sys.argv[0]))
    exit(-1)

URL = 'http://%s:%d' % (sys.argv[1], int(sys.argv[2]))
RestToolbox.SetCredentials(sys.argv[3], sys.argv[4])
peer_name = sys.argv[5]
foo_url = sys.argv[6]

# Queue that is shared between the producer and the consumer
# threads. It holds the instances that are still to be sent.
queue = queue.Queue()

# The producer thread. It monitors the arrival of new instances into
# Orthanc, and pushes their ID into the shared queue. This code is
# based upon the "ChangesLoop.py" and "HighPerformanceAutoRouting.py"
# sample code.

def Producer(queue):
    current = 0

    while True:
        r = RestToolbox.DoGet(URL + '/changes', {
            'since' : current,
            'limit' : 4   # Retrieve at most 4 changes at once
            })

        for change in r['Changes']:
            # We are only interested in the arrival of new instances
            if change['ChangeType'] == 'NewInstance':
                queue.put(change['ID'])

        current = r['Last']

        if r['Done']:
            time.sleep(1)

# The consumer thread. It continuously reads the instances from the
# queue, and send them to the remote Orthanc peer. Each time a packet of
# instances is sent, a single DICOM connexion is used, hence improving
# the performance.
def Consumer(queue):
    TIMEOUT = 0.1
    while True:
        instances = []
        while True:
            try:
                # Block for a while, waiting for the arrival of a new
                # instance
                instance = queue.get(True, TIMEOUT)

                # A new instance has arrived: Record its ID
                instances.append(instance)
                queue.task_done()

            except Exception as e:
                break

        if len(instances) > 0:
            request_body = {}
            request_body['Resources'] = []
            request_body['Compression'] = "gzip"
            request_body['Peer'] = peer_name
            for instance in instances:
                 request_body['Resources'].append({"Level":"Instance","ID":instance})
            print('Sending a packet of %d instances' % len(instances))
            start = time.time()

            # Send current instances through the Tranfers Accelerator Plugin REST API
            RestToolbox.DoPost('%s/transfers/send' % URL, json.dumps(request_body))

            time.sleep(1)
            listofinstance = RestToolbox.DoGet('%s/instances' % URL)
            #listofinstancepeer = RestToolbox.DoGet('http://10.8.0.8:8042/instances')

            RestToolbox.DoDelete('%s/exports' % URL)
            for instance in instances:
                serie = RestToolbox.DoGet('%s/instances/%s' % (URL, instance) )['ParentSeries']
                study = RestToolbox.DoGet('%s/series/%s' % (URL, serie) )['ParentStudy']

                while (instance not in listofinstance) or (study in RestToolbox.DoGet('%s/studies' % foo_url)):
                   time.sleep(1)
                   listofinstance = RestToolbox.DoGet('%s/instances' % URL)
                   #listofinstancepeer = RestToolbox.DoGet('http://10.8.0.8:8042/instances')
                RestToolbox.DoDelete('%s/instances/%s' % (URL, instance))

            end = time.time()
            print('The packet of %d instances has been sent in %d seconds' % (len(instances), end - start))


# Thread to display the progress
def PrintProgress(queue):
    while True:
        print('Current queue size: %d' % (queue.qsize()))
        time.sleep(1)


# Start the various threads
progress = threading.Thread(None, PrintProgress, None, (queue, ))
progress.daemon = True
progress.start()

producer = threading.Thread(None, Producer, None, (queue, ))
producer.daemon = True
producer.start()

consumer = threading.Thread(None, Consumer, None, (queue, ))
consumer.daemon = True
consumer.start()

# Active waiting for Ctrl-C
while True:
    time.sleep(0.1)
