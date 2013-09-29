import url as URL

from irc import Callback

cb = Callback()

@cb.threadsafe
@cb.command("shorten shortgo bl bitly bit.ly".split(), "(.+)", 
			usage="12bit.ly⎟ Usage: !shorten <url>",
			error="05bit.ly⎟ Unable to generate shortlink.")
def shortgo(message, url):
    return "12bit.ly⎟ %s" % URL.format(URL.shorten(url))

__initialise__ = cb.initialise
__callbacks__ = {"privmsg": [shortgo]}