"""
Functions for manipulating urls.
"""

import re
import difflib
import urllib.parse as urllib

import requests
import json
import yaml


apikeys = yaml.safe_load(open("apikeys.conf"))
regex = re.compile(r"\b(\w+://)?\w+(\.\w+)+/[^\s]*\b")
    
def uncaps(url):
    page = json.loads(requests.get("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s" % urllib.quote(url)).text)
    urls = [i["unescapedUrl"] for i in page["responseData"]["results"]]
    urls = [(difflib.SequenceMatcher(None, url.upper(), x.upper()).ratio(), x) for x in urls]
    urls = [x for x in urls if x[0] > 0.8]
    if urls: return max(urls, key=lambda x:x[0])[1]
    else: return url.lower()
    
def format(url):
    return "\x0312\x1f%s\x1f\x03" % url

def shorten(url):
    args = {'login': apikeys["bit.ly"]["user"], 'apiKey':apikeys["bit.ly"]["key"], 'format': "json"}
    if not url.lower().startswith("http://"):
        url = "http://" + url
    data = requests.get("http://api.bitly.com/v3/shorten?" + urllib.urlencode(args) + "&longUrl=" + urllib.quote(url)).text
    data = json.loads(data)
    return data["data"]["url"]
