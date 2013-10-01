"""
Functions for manipulating urls.
"""

import difflib
import re
import sys
import urllib.parse as urllib

import requests
import yaml

try:
    apikeys = yaml.safe_load(open("config/apikeys.conf"))["bit.ly"]
except:
    print("Warning: invalid or nonexistant api key.", file=sys.stderr)
    print("Defining url.shorten as identity function", file=sys.stderr)
    apikeys = None

regex = re.compile(r"\b(\w+://)?\w+(\.\w+)+/[^\s]*\b")
    
def uncaps(url):
    page = requests.get("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s" % urllib.quote(url)).json()
    urls = [i["unescapedUrl"] for i in page["responseData"]["results"]]
    urls = [(difflib.SequenceMatcher(None, url.upper(), x.upper()).ratio(), x) for x in urls]
    urls = [x for x in urls if x[0] > 0.8]
    if urls: 
        return max(urls, key=lambda x:x[0])[1]
    else: 
        return url.lower()
    
def format(url):
    return "\x0312\x1f%s\x1f\x03" % url

if apikeys is not None:
    def shorten(url):
        args = {'login': apikeys["user"], 'apiKey':apikeys["key"], 'format': "json"}
        if not url.lower().startswith("http://"):
            url = "http://" + url
        data = requests.get("http://api.bitly.com/v3/shorten?" + urllib.urlencode(args) + "&longUrl=" + urllib.quote(url)).json()
        return data["data"]["url"]
else:
    shorten = lambda x:x