import sys
import yaml
import requests

try:
    apikeys = yaml.safe_load(open("config/apikeys.conf"))["imgur"]
except:
    print("Warning: invalid or nonexistant api key.", file=sys.stderr)
    print("Skipping util.services.imgur", file=sys.stderr)
    apikeys = None
else:
    def upload(data):
        headers = {"Authorization": "Client-ID %s" % apikeys["client_id"]}

        res = requests.post(
            "https://api.imgur.com/3/upload.json", 
            headers = headers,
            data = {'image': data}
        )
        return res.json()