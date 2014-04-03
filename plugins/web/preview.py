import sys
import yaml
import functools
import requests

from bot.events import Callback, command


class Summary(Callback):
    API_URL = "http://api.smmry.com/"

    def __init__(self, server, key=None):
        self.key = key

        super().__init__(server)

    @command("preview", r"(.+)")
    def preview(self, server, message, url):
        params = {"SM_API_KEY": self.key,
                  "SM_URL": url,
                  "SM_LENGTH": 1}
        summary = requests.get(self.API_URL, params=params).json()
        
        return "12│ " + summary["sm_api_content"]
        
try:
    apikeys = yaml.safe_load(open("config/apikeys.conf"))["smmry"]
    __initialise__ = functools.partial(Summary, key=apikeys["key"])
except:
    print("Preview requires a smmry API key. Skipping module.", sys.stderr)