
'''
sudo apt-get  update
sudo apt-get install -y python
sudo apt-get install -y fabric
sudo apt-get install -y python-pip
pip install paramiko
pip install requests
'''
import requests
import json
import time
import paramiko


def setup_servers():
    url = 'https://auth.api.rackspacecloud.com/v2.0/tokens'
    url_server= 'https://ord.servers.api.rackspacecloud.com/v2//servers'
    num_slaves = 1
    api_key = '1'
    user_name ='2'
    accountid = '3'

    body = {"auth":{"RAX-KSKEY:apiKeyCredentials":{"username": user_name,
                                       "apiKey": api_key }}}
    headers = {'content-type': 'application/json',
               'accept': 'application/json'}
    payload = json.dumps(body)
    result = requests.post(url, data=payload, headers=headers)
    print result.status_code
    try:
        tokenid = result.json().get('access').get('token').get('id')

    except:
        pass
    print tokenid


    server_slaves_id=[]
    server_names=[]
    for i in range(num_slaves):
        server_name ="slave_server-{0}".format(i)
        server_names.append(server_name)
        body_serv ={ "server" : {
                "name" : server_name,
                "imageRef" : "8ae428cd-0490-4f3a-818f-28213a7286b0",
                "flavorRef" : "2",
                "adminPass": "Test1234",
                "OS-DCF:diskConfig" : "AUTO",
                "metadata" : {
                    "My Server Name" : "Performance Test Server"
                }
            }}

        headers_serv= {'content-type': 'application/json',
                       'accept': 'application/json',
                       'X-Auth-Token': tokenid }

        payload_serv = json.dumps(body_serv)
        result = requests.post(url_server, data=payload_serv, headers=headers_serv)
        print result.status_code
        server_id = result.json().get('server').get('id')
        server_slaves_id.append(server_id)
        serv_url = url_server+'/'+server_id
        print serv_url
    time.sleep(200)

    ipv4 = []
    for server_id in server_slaves_id:
        serv_url = url_server+'/'+server_id
        get_serv = requests.get(serv_url, data=payload_serv, headers=headers_serv)
        print get_serv.status_code
        serv_ipv4 = get_serv.json().get('server').get('accessIPv4')
        ipv4.append(serv_ipv4)
    print server_names
    print ipv4
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for i in range (len(ipv4)):
        client.connect(str(ipv4[i]), username='root', password='Test1234')
        stdin, stdout, stderr = client.exec_command('ls -la')
        for line in stdout:
            print '... ' + line.strip('\n')
    client.close()

if __name__ == '__main__':
    setup_servers()

