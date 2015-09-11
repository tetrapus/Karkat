from bot.events import command, Callback
import json

infofile = "info.json"
undofile = "undo.json"
protectionfile = "users.json"

def check_whois(gen, server, msg, user):
    server.whois_waiting[server.lower(msg.address.nick)] = (gen, msg)
    server.printer.raw_message("WHOIS :%s" % msg.address.nick)

@Callback.inline
def finish_whois(server, line):
    words = line.split()
    nick = server.lower(words[3])
    if nick in server.whois_waiting:
        gen, msg = server.whois_waiting[nick]
        del server.whois_waiting[nick]
        output = server.printer.buffer(msg.context, "PRIVMSG")
        with output as out:
            for i in gen:
                out += i

def isprotected(server, user):
    try:
        protected = json.load(open(server.get_config_dir(protectionfile)))
    except:
        protected = {}
    return server.lower(user) in protected and protected[server.lower(user)]

def set_protected(server, user):
    """ Add protection if not defined """
    try:
        protected = json.load(open(server.get_config_dir(protectionfile)))
    except:
        protected = {}
    if server.lower(user) not in protected:
        protected[server.lower(user)] = True
    json.dump(protected, open(server.get_config_dir(protectionfile), "w"))

@command("protect", r"(on|off|none)?")
def toggle_protection(server, msg, state):
    user = msg.address.nick
    luser = server.lower(user)
    registered = server.registered.get(luser, False)
    try:
        protected = json.load(open(server.get_config_dir(protectionfile)))
    except:
        protected = {}
    if state == "on":
        protected[luser] = True
    elif state == "off":
        protected[luser] = False
    elif state == "none":
        del protected[luser]
    else:
        protected[luser] = not protected.get(luser, False)
    json.dump(protected, open(server.get_config_dir(protectionfile), "w"))
    return "│ Account protection for %s is %s" %(user, "CLEARED" if luser not in protected else ["OFF", "ON"][protected[luser]])
    

@command("info", r"(.*)", prefixes=("", "."))
def getinfo(server, msg, user):
    try:
        data = json.load(open(server.get_config_dir(infofile)))
    except:
        data = {}
    user = user or msg.address.nick
    luser = server.lower(user)
    protected = isprotected(server, user)
    if luser not in data:
        return "I don't have info about %s. %s can use \x0312!setinfo \x1fblurb\x0f to add their info, or try !info %s if another bot provides this service." % (user, user, user)
    elif protected:
        return "\x0312%s\x03: %s" % (user, data[luser])
    else:
        return "%s: %s" % (user, data[luser])

@command("setinfo", r"(.*)", prefixes=("!", "."))
def setinfo(server, msg, info):
    yield check_whois
    try:
        data = json.load(open(server.get_config_dir(infofile)))
    except:
        data = {}
    try:
        undo = json.load(open(server.get_config_dir(undofile)))
    except:
        undo = {}
    user = msg.address.nick
    luser = server.lower(user)
    protected = isprotected(server, user)
    registered = server.registered.get(luser, False)

    if protected and not registered:
        if msg.prefix != "!":
            yield "│ This nickname is protected by the owner. Please identify with NickServ to update your info."
        return

    if luser in data:
        undo[luser] = data[luser]

    if not info:
        del data[luser]
        if msg.prefix != "!":
            yield "│ Your information has been deleted."
    else:
        data[luser] = info
        if msg.prefix != "!":
            yield "│ Your information has been updated."

    if registered:
        set_protected(server, user)

    json.dump(data, open(server.get_config_dir(infofile), "w"))
    json.dump(undo, open(server.get_config_dir(undofile), "w"))

@command("undo", prefixes=("!", "."))
def undoinfo(server, msg):
    yield lambda x, y, z: check_whois(x, y, z, "")
    try:
        data = json.load(open(server.get_config_dir(infofile)))
    except:
        data = {}
    try:
        undo = json.load(open(server.get_config_dir(undofile)))
    except:
        undo = {}
    user = msg.address.nick
    luser = server.lower(user)
    protected = isprotected(server, user)
    registered = server.registered.get(luser, False)

    if protected and not registered:
        if msg.prefix != "!":
            yield "│ This nickname is protected by the owner. Please identify with NickServ to update your info."
        return

    if luser not in undo or luser not in data:
        yield "│ I have no history recorded for your username."
        return
    undo[luser], data[luser] = data[luser], undo[luser]

    if not data[luser]:
        if msg.prefix != "!":
            yield "│ Your information has been deleted."
    else:
        if msg.prefix != "!":
            yield "│ Your information has been updated."

    if registered:
        set_protected(server, user)

    json.dump(data, open(server.get_config_dir(infofile), "w"))
    json.dump(undo, open(server.get_config_dir(undofile), "w"))

__callbacks__ = {"privmsg": [getinfo, setinfo, toggle_protection, undoinfo], "318": [finish_whois]}

def __initialise__(server):
    server.whois_waiting = {}