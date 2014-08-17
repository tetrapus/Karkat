import sys
import yaml
import requests

from bot.events import command


try:
    apikeys = yaml.safe_load(open("config/apikeys.conf"))["yo"]
except:
    print("Error: invalid or nonexistant last.fm api key.", file=sys.stderr)
    raise ImportError("Could not load module.")

@command("yo", r"(\S+)")
def yo(server, message, username):
    data = requests.post("http://api.justyo.co/yo/", data={"api_token": list(apikeys.values())[0], 'username':username}).text
    if data == '{"result": "OK"}': # result is not always json
        return "13│🖐│ Yo'd at %s" % username
    elif data == '{"code": 141, "error": "NO SUCH USER"}':
        return "04│🖐│ I ain't see no %s" % username
    else:
        return "04│🖐│ Yo's fucked up."

__callbacks__ = {"privmsg": [yo]}
