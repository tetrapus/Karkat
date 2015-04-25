from bot.events import command
import json

infofile = "info.json"

@command("info", r"(.*)", prefixes=("", "."))
def info(server, msg, user):
    try:
        data = json.load(open(server.get_config_dir(infofile)))
    except:
        data = {}
    user = user or msg.address.nick
    luser = server.lower(user)
    if luser not in data:
        return "I don't have info about %s. %s can use \x0312!setinfo \x1fblurb\x0f to add their info, or try !info %s if another bot provides this service." % (user, user, user)
    else:
        return "%s: %s" % (user, data[luser])

@command("setinfo", r"(.*)", prefixes=("!", "."))
def setinfo(server, msg, info):
    try:
        data = json.load(open(server.get_config_dir(infofile)))
    except:
        data = {}
    user = msg.address.nick
    luser = server.lower(user)
    if not info:
        del data[luser]
        yield "│ Your information has been deleted."
    else:
        data[luser] = info
        if msg.prefix != "!":
            yield "│ Your information has been updated."
    json.dump(data, open(server.get_config_dir(infofile), "w"))

__callbacks__ = {"privmsg": [info, setinfo]}