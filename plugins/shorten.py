from irc import Callback
import url as URL

cb = Callback()

@cb.threadsafe
@cb.command("shorten shortgo bl bitly bit.ly".split(), "(.+)", help="12bit.ly⎟ Usage: !shorten <url>")
def shortgo(message, url):
    try:
        return "12bit.ly⎟ %s" % URL.format(URL.shorten(url))
    except:
        return "05bit.ly⎟ That didn't work somehow."

__initialise__ = cb.initialise
__callbacks__ = {"privmsg": [shortgo]}