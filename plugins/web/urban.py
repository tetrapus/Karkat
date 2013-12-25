"""
Get definitions from urbandictionary
A James module.
"""
from util.irc import command
from util.services.url import shorten
import requests
import traceback
import random


@command(['urban', 'urbandictionary', 'ud'], r"^(.*?)(\s+\d+)?$")
def urban_lookup(bot, msg, arg, index):
    ''' UrbanDictionary lookup. '''
    if not arg:
        return "Usage: urban [phrase] [index?]"

    url = 'http://www.urbandictionary.com/iphone/search/define'
    params = {'term': arg}
    nick = msg.address.nick
    try:
        index = int(index.strip()) - 1
    except:
        index = 0

    request = requests.get(url, params=params)

    data = request.json()
    defs = None
    output = ""
    try:
        defs = data['list']

        if data['result_type'] == 'no_results':
            return failmsg() % (nick, params['term'])

        output = defs[index]['word'] + ' [' + str(index+1) + ']: ' + defs[index]['definition']
    except:
        traceback.print_exc()
        return failmsg() % (nick, params['term'])

    output = output.strip()
    output = output.rstrip()
    output = ' '.join(output.split())

    if len(output) > 300:
        tinyurl = shorten(defs[index]['permalink'])
        output = output[:output.rfind(' ', 0, 180)] + '...\r\nRead more: %s'\
            % (tinyurl)
        return "%s: %s" % (nick, output)

    else:
        return "%s: %s" % (nick, output)

def failmsg():
    return random.choice([
        "%s: No definition found for %s.",
        "%s: The heck is '%s'?!",
        "%s: %s. wut.",
        "%s: %s? I dunno...",
        "%s: Stop searching weird things. What even is '%s'?",
        "%s: Computer says no. '%s' not found.",
        "*sigh* someone tell %s what '%s' means",
        "%s: This is a family channel. Don't look up '%s'",
        "%s: Trust me, you don't want to know what '%s' means.",
        "%s: %s [1]: Something looked up by n00bs.",
        "%s: %s [1]: An obscure type of fish.",
        "No %s, no '%s' for you.",
        "Shh %s, nobody's meant to know about '%s'...",
        "Really %s? %s?"])

#@command(['urbanrandom', 'urbandictionaryrandom', 'udr'])
#def urban_random(server, message):
#    ''' Random UrbanDictionary lookup. '''
#    word = requests.get("http://api.urbandictionary.com/v0/random").json()['list'][0]['word']
#    urban_lookup(server, ":" + message.message.split(":", 2)[1] + ":.ud " + word)

__callbacks__ = {"privmsg": [urban_lookup]}