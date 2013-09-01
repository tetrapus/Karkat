from irc import Callback
import url as URL

import yaml

apikeys = yaml.safe_load(open("apikeys.conf"))
cb = Callback()

@cb.threadsafe
@cb.command("shorten shortgo bl bitly bit.ly".split(), "(.+)")
def shortgo(message, url):
    try:
        return "「 ShortGo 」 %s" % URL.format(URL.shorten(url))
    except:
        return "「 ShortGo 」 That didn't work somehow."

__initialise__ = cb.initialise
__callbacks__ = {"privmsg": [shortgo]}