# This code considers the "push mode" in the "Transfer Accelerator" plugin. If the pull mode is used or the
# "Tranfer Accelerator" plugin is not used, some changes will be necessary to capture the log.

import collections
import json
import os
import requests
import sys
import time

def requestseries(job_id):

   base_url,username,password = retrieveURL(job_id)
   response = requests.get(f"{base_url}/series", auth=(username, password))

   if response.status_code == 200:
       return(response.json())

   else:
       print(f"Series request failed with status code {response.status_code}")


def getseriecontent(job_id, serie):

   base_url, username, password = retrieveURL(job_id)
   response = requests.get(f"{base_url}/series/{serie}", auth=(username, password))

   if response.status_code == 200:
       return(response.json())


   else:
       print(f"Series request failed with status code {response.status_code}")


def getjobcontent(job_id):

   base_url, username, password = retrievelocalURL()
   response = requests.get(f"{base_url}/jobs/{job_id}", auth=(username, password))

   if response.status_code == 200:
       return (response.json())

   else:
       print(f"Job content request failed with status code {response.status_code}")


def findstudies(job_id):

   job = getjobcontent(job_id)
   instances = job['Content']['Resources']
   studies = set()

   series = requestseries(job_id)
   seriecontent = collections.defaultdict(list)

   for s in series:
       seriecontent[s] = getseriecontent(job_id, s)

   for i in instances:
       for s in series:
           serie = seriecontent[s]
           if i['ID'] in serie['Instances']:
               studies.add(serie['ParentStudy'])
               break

   return studies


def retrievelocalURL():

    host = jsonFile['host']
    port = jsonFile['port']
    
    base_url = f'http://{host}:{port}'
    username = 'orthanc'
    password = 'orthanc'
    return (base_url, username, password)


def retrieveURL(job_id):

    host = jsonFile['host']
    port = jsonFile['port']
    peer_host = jsonFile['peers'][0]['host']
    peer_port = jsonFile['peers'][0]['port']

    jobinfo = getjobcontent(job_id)

    if jobinfo == None:
        return None, None, None

    if jobinfo['State'] == 'Success':

        base_url = f'http://{peer_host}:{peer_port}'
        username = 'orthanc'
        password = 'orthanc'
        return (base_url, username, password)

    else:

        base_url = f'http://{host}:{port}'
        username = 'orthanc'
        password = 'orthanc'
        return (base_url, username, password)



def savelog_v2(job_id, dic_name_id, sentlist):

   log = collections.defaultdict()

   base_url, username, password = retrieveURL(job_id)
   base_url_local, username_local, password_local = retrievelocalURL()

   if base_url == None or base_url_local == None:
       return

   jobinfo = getjobcontent(job_id)
   if jobinfo:
       studies = findstudies(job_id)


   #Waiting for finishing transmission

   studieslist = (requests.get(f"{base_url_local}/studies", auth=(username_local, password_local))).json()
   studies_to_remove = set()
   for study in studies:
       if study not in studieslist:
           studies_to_remove.add(study)
   studies -= studies_to_remove

   if getjobcontent(job_id)['State'] == 'Success':
       for study in studies:

           while (requests.get(f"{base_url_local}/studies/{study}", auth=(username_local, password_local))).json()['IsStable'] == 'false':
               time.sleep(1)
           while (requests.get(f"{base_url_local}/studies/{study}/statistics", auth=(username_local, password_local))).json()['CountInstances'] != \
                   (requests.get(f"{base_url}/studies/{study}/statistics", auth=(username, password))).json()['CountInstances']:
               time.sleep(2)



   for study in list(studies):

       name = (requests.get(f"{base_url_local}/system", auth=(username_local, password_local)).json())['Name']
       id = dic_name_id[name]

       name_peer = jobinfo['Content']['Peer']
       id_peer = dic_name_id[name_peer]

       log['gateway'] = id
       log['peer'] = id_peer
       log['status'] = True if jobinfo['State'] == 'Success' else False

       log['studyinstanceuid'] = study
       log['seriesinstanceuid'] = (requests.get(f"{base_url}/studies/{study}", auth=(username, password)).json())['Series']
       log['instances'] = (requests.get(f"{base_url}/studies/{study}/statistics", auth=(username, password)).json())['CountInstances']
       log['totalsizemb'] = (requests.get(f"{base_url}/studies/{study}/statistics", auth=(username, password)).json())['DiskSizeMB']


       #Saving locally
       if jobinfo['State'] == 'Success':
           logJSON = "log-success-output"
       else:
           logJSON = "log-failure-output"

       with open(logJSON, "a") as file:
           json.dump(log, file, indent=4)
       print(f"Response saved to {logJSON}")

       #Sending to the manager
       response = requests.post("http://52.67.253.89:8080/log", json=log)

       if response.status_code == 200:
           print('POST request successful!')
       else:
           print(f'Error in POST request. Status code: {response.status_code}')
           print(response.text)

   return studies


if __name__ == '__main__':

   jsonFile = sys.argv[2]
   jsonFile = json.loads(jsonFile)
   dic_name_id = sys.argv[4]
   dic_name_id = json.loads(dic_name_id)
   sentlist = collections.defaultdict()

   path_to_log = os.getcwd() + '/orthanc.log'
   prev_position = 0
   curren_studies = []

   while True:
       with open(path_to_log, 'r') as file:
           file.seek(prev_position)

           for line in file:
               print(line)
               if ("Job has completed with success" in line) or ("Job has completed with failure" in line):
                    if "Job has completed with success" in line:
                        print("Job has completed with success!")

                    else:
                        print("Job has completed with failure!")

                    job = line.split()[-1]
                    studies = savelog_v2(job, dic_name_id, sentlist)
                        
                    #Delete studies
                    if studies:
                        for study in studies:
                            requests.delete('http://10.8.0.8:8042/studies/%s' % (study), auth=('orthanc', 'orthanc'))




           prev_position = file.tell()

       time.sleep(1)
