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

searchapi_url = "http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s"
bitlyapi_url = "http://api.bitly.com/v3/shorten?"

regex = re.compile(r"\b(\w+://)?\w+(\.\w+)+/[^\s]*\b")

def uncaps(url):
    """ Use google to check the proper case of a URL. """
    page = requests.get(searchapi_url % urllib.quote(url)).json()
    urls = [i["unescapedUrl"] for i in page["responseData"]["results"]]
    urls = [x.upper() for x in urls]
    matches = difflib.get_close_matches(url.upper(), urls, n=1, cutoff=0.8)
    if urls:
        return matches[0]
    else:
        return url.lower()

def format(url):
    """ IRC format a url. """
    return "\x0312\x1f%s\x1f\x03" % url

if apikeys is not None:
    def shorten(url):
        """ Shorten a URL with bit.ly """
        if not url.lower().startswith("http"):
            url = "http://" + url

        args = {'login': apikeys["user"],
                'apiKey':apikeys["key"],
                'format': "json",
                'longUrl': url}

        data = requests.get(bitlyapi_url + urllib.urlencode(args)).json()
        return data["data"]["url"]
else:
    shorten = lambda x:x
