from irc import Callback
import url as URL

import yaml

apikeys = yaml.safe_load(open("apikeys.conf"))
cb = Callback()

@cb.threadsafe
@cb.command("shorten shortgo bl bitly bit.ly".split(), "(.+)", help="12bit.ly05⎟ Usage: !shorten <url>")
def shortgo(message, url):
    try:
        return "12bit.ly⎟ %s" % URL.format(URL.shorten(url))
    except:
        return "12bit.ly⎟ That didn't work somehow."

__initialise__ = cb.initialise
__callbacks__ = {"privmsg": [shortgo]}