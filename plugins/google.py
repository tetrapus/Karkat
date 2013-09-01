import json
import requests
import urllib.parse as urllib

import url

from irc import Callback

cb = Callback()

@cb.threadsafe
def google(message, query):
    print("Triggered.")
    request = requests.get("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s" % urllib.quote(query))
    page = json.loads(request.text)
    # TODO: Error handling

    first = True
    for i in page["responseData"]["results"]: 
        yield "12%s⎟ %s - %s" % ("Google" if first else "      ", 
        												 i["titleNoFormatting"], 
        												 url.format(url.shorten(i["unescapedUrl"])))
        if first: 
        	first = False
        if message.text[0] == "@":
        	return
    if first:
        yield "12Google⎟ No results found."
google = cb.command("google", "(.+)")(google)


__initialise__ = cb.initialise
__callbacks__  = cb.callbacks