import csv
import requests
import json


def authenticate():
    url = ''
    tokens = {}
    with open('accountids.csv', 'r') as f:

            reader = csv.DictReader(f)

            for row in reader:
                print row
                api_key = row.get('apikey')
                user_name = row.get('username')
                accountid = row.get('accountid')
                print user_name
                print accountid
                body = {"auth":{"RAX-KSKEY:apiKeyCredentials":{"username": user_name,
                                                   "apiKey": api_key }}}
                headers = {'content-type': 'application/json',
                           'accept': 'application/json'}
                payload = json.dumps(body)
                result = requests.post(url, data=payload, headers=headers)
                print result.status_code
                try:
                    tokenid = result.json().get('access').get('token').get('id')
                    tokens [accountid] = tokenid

                except:
                    pass
    print tokens
    filePath = open("token.csv", 'w+')
    filePath.write("accountid,token\n")
    writer = csv.writer(filePath)
    for key, value in tokens.items():
       writer.writerow([key, value])





if __name__ == '__main__':
    authenticate()

