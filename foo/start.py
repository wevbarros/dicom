import collections
import copy
import hashlib
import json
import os
import random
import requests
import ruamel.yaml
import subprocess
import time

def generate_hash_code():

    timestamp = (int(time.time() * 1000)) * (random.randint(1, 1000))
    timestamp_str = str(timestamp)

    hash_obj = hashlib.sha256()
    hash_obj.update(timestamp_str.encode())

    hash_code = hash_obj.hexdigest()

    with open("hash_code.txt", "w") as file:
        file.write(hash_code)
    print(f"Hash code: {hash_code} has been saved to 'hash_code.txt'")
    return hash_code

def get_server_data(key):

    url = f'http://52.67.253.89:8080/gateway/{key}'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception("Failed to fetch data from the server")


def stop_docker():
    
    command = "docker stop $(docker ps -q)"
    try:
        #subprocess.run(command, shell=True, check=True, cwd=r'C:\project-canon\ilikauploader-orthanc\bar') # Windows env (change the path)
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
    time.sleep(10)

def start_docker():
    command = "docker-compose -f 'orthanc.yml' up"

    # Open subprocess with stdout and stderr redirected to a file and detached set to True
    with open('orthanc.log', 'w') as log_file:
        process = subprocess.Popen(command, shell=True, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
        return process


def start_log(jsonData, dict_idname):
    jsonFile = json.dumps(jsonData)
    dictFile = json.dumps(dict_idname)

    command = ['python3', 'log.py', '--jsonFile', jsonFile, '--dictFile', dictFile]
    #subprocess.run(command)
    subprocess.Popen(command)

def check_update(key, current_content):

    url = f'http://52.67.253.89:8080/gateway/{key}'
    response = requests.get(url)
    if response.status_code == 200:
        if current_content == response.json():
            return None
        else:
            return response.json()
    else:
        raise Exception("Failed to fetch data from the server")

def chengewiraguardfile():

    file_path = os.getcwd() + '/wireguard/wg0.conf'

    with open(file_path, 'r') as file:
        content = file.readlines()

    for i in range(len(content)):
        if 'AllowedIPs' in content[i]:
            content[i] = 'AllowedIPs = 0.0.0.0/0\n'
            break

    with open(file_path, 'w') as file:
        file.writelines(content)

    print(f'The content of {file_path} has been modified.')

def builddictID(jsonData):

    dic = collections.defaultdict()

    dic[jsonData['name']] = jsonData['id']
    for p in jsonData['peers']:
        dic[p['name']] = p['id']

    return dic
def buildwireguard(key):

    if os.path.exists(os.getcwd() + '/wireguard/wg0.conf') or os.path.exists(os.getcwd() + '/wireguard/wg_conf/wg0.conf'):
        return

    else:
        url = f"http://52.67.253.89:8080/gateway/vpn/config/{key}"

        response = requests.get(url)
        if response.status_code == 200:

            file_path = os.getcwd() + '/wireguard' + '/wg0.conf'
            with open(file_path, 'wb') as file:
                file.write(response.content)
            print(f"File downloaded and saved to {file_path}")
            chengewiraguardfile()
        else:
            print(f"Failed to download the file. Status code: {response.status_code}")

def update_yaml(jsonData, key):

    name = jsonData['name']
    user = 'orthanc'
    password = 'orthanc'
    host = jsonData['host']
    port = jsonData['port']

    yaml = ruamel.yaml.YAML()
    with open('orthanc.yml', 'r') as file:
        config = yaml.load(file)

    registered_users_data = {
        f"{user}": f"{password}"
    }
    config['services']['orthanc-foo']['environment']['ORTHANC__REGISTERED_USERS'] = json.dumps(registered_users_data)

    # Peer linked
    if len(jsonData['peers']) > 0:
        peer_name = jsonData['peers'][0]['name']  # if jsonData['peers'] and jsonData['peers'][0]['name'] else ""
        peer_host = jsonData['peers'][0]['host']  # if jsonData['peers'] and jsonData['peers'][0]['host'] else ""
        peer_port = '8042' #jsonData['peers'][0]['port']  # if jsonData['peers'] and jsonData['peers'][0]['port'] else ""
        peer_user = 'orthanc'
        peer_password = 'orthanc'
        # remoteself = jsonData['name'] # pull mode

        orthanc_peer_data = {
            f"{peer_name}": {
                "Url": f"http://{peer_host}:{peer_port}",
                "Username": peer_user,
                "Password": peer_password
            }
        }

        command = "/bin/sh -c 'pip3 install requests && pip3 install httplib2 --upgrade && python3 /home/orthanc/src/gateway-driver.py 127.0.0.1 8042 {} {} {}'".format(user, password, peer_name)


        config['services']['orthanc-foo']['environment']['ORTHANC__ORTHANC_PEERS'] = json.dumps(orthanc_peer_data)

    ###
    else:
        if 'ORTHANC__ORTHANC_PEERS' in config['services']['orthanc-foo']['environment']:
            del config['services']['orthanc-foo']['environment']['ORTHANC__ORTHANC_PEERS']
        command = "/bin/sh -c 'tail -f /dev/null'"


    config['services']['wireguard']['command'] = "/bin/sh -c 'ping google.com'"
    config['services']['gateway-driver']['command'] = command
    config['services']['orthanc-foo']['environment']['ORTHANC__NAME'] = name

    with open('orthanc.yml', 'w') as file:
        yaml.dump(config, file)

if __name__ == '__main__':

    if os.path.isfile("hash_code.txt"):
            with open("hash_code.txt", "r") as file:
                hash_code = file.read()
            print(f"Hash code already exists: {hash_code}")
            key = hash_code
    else:
        key = generate_hash_code()

    if (requests.get(f'http://52.67.253.89:8080/gateway/{key}')).status_code != 200:
        print('Waiting for the ID/key entry')
        while (requests.get(f'http://52.67.253.89:8080/gateway/{key}')).status_code != 200:
            pass

    buildwireguard(key)


    jsonData = get_server_data(key)

    dict_idname = builddictID(jsonData)

    update_yaml(jsonData,key)

    start_docker()

    start_log(jsonData, dict_idname)

    while True:
        time.sleep(5)
        newJson = check_update(key, jsonData)
        if newJson is not None and newJson!= jsonData:
            stop_docker()
            update_yaml(newJson,key)
            start_docker()
            jsonData = copy.deepcopy(newJson)
