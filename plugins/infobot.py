"""
Provides .info and related commands. Allows users to set information about themselves that may be
retrieved by other users.
"""
import json

from bot.events import command, Callback


INFO_PATH = "info.json"
UNDO_PATH = "undo.json"
PROTECTION_PATH = "users.json"


def check_whois(gen, server, msg, _):
    ''' Generate and catch a whois event for a given user '''
    server.whois_waiting[server.lower(msg.address.nick)] = (gen, msg)
    server.printer.raw_message("WHOIS :%s" % msg.address.nick)


@Callback.inline
def finish_whois(server, line):
    ''' Resume execution of a generator waiting on a WHOIS event '''
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
    ''' Check if the given user has opted to protect their info. '''
    try:
        protected = json.load(open(server.get_config_dir(PROTECTION_PATH)))
    except:
        protected = {}
    return server.lower(user) in protected and protected[server.lower(user)]


def set_protected(server, user):
    """ Add protection if not defined """
    try:
        protected = json.load(open(server.get_config_dir(PROTECTION_PATH)))
    except:
        protected = {}
    if server.lower(user) not in protected:
        protected[server.lower(user)] = True
    json.dump(protected, open(server.get_config_dir(PROTECTION_PATH), "w"))


@command("protect", r"(on|off|none)?")
def toggle_protection(server, msg, state):
    ''' Toggle a user's protection state '''
    user = msg.address.nick
    luser = server.lower(user)
    # NOTE: I have no idea what the following code does?
    registered = server.registered.get(luser, False)
    try:
        protected = json.load(open(server.get_config_dir(PROTECTION_PATH)))
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
    json.dump(protected, open(server.get_config_dir(PROTECTION_PATH), "w"))
    return "│ Account protection for {user} is {action}".format(
        user=user,
        action="CLEARED" if luser not in protected else ["OFF", "ON"][protected[luser]],
    )


@command("info", r"(.*)")
def getinfo(server, msg, user):
    ''' Retrieve a user's info. '''
    try:
        data = json.load(open(server.get_config_dir(INFO_PATH)))
    except:
        data = {}
    user = user or msg.address.nick
    luser = server.lower(user)
    protected = isprotected(server, user)
    if luser not in data:
        return (
            "I don't have info about {user}. "
            "{user} can use \x0312!setinfo \x1fblurb\x0f to add their info, "
            "or try !info {user} if another bot provides this service.".format(user=user)
        )
    elif protected:
        return "\x0312{user}\x03: {info}".format(user=user, info=data[luser])
    else:
        return "{user}: {info}".format(user=user, info=data[luser])


@command("setinfo", r"(.*)")
def setinfo(server, msg, info):
    ''' Set your .info text. '''
    yield check_whois
    try:
        data = json.load(open(server.get_config_dir(INFO_PATH)))
    except:
        data = {}
    try:
        undo = json.load(open(server.get_config_dir(UNDO_PATH)))
    except:
        undo = {}
    user = msg.address.nick
    luser = server.lower(user)
    protected = isprotected(server, user)
    registered = server.registered.get(luser, False)

    if protected and not registered:
        yield (
            "│ This nickname is protected by the owner. "
            "Please identify with NickServ to update your info."
        )
        return

    if luser in data:
        undo[luser] = data[luser]

    if not info:
        del data[luser]
        yield "│ Your information has been deleted."
    else:
        data[luser] = info
        yield "│ Your information has been updated."

    if registered:
        set_protected(server, user)

    json.dump(data, open(server.get_config_dir(INFO_PATH), "w"))
    json.dump(undo, open(server.get_config_dir(UNDO_PATH), "w"))


@command("undo")
def undoinfo(server, msg):
    ''' Undo the last .setinfo '''
    yield lambda x, y, z: check_whois(x, y, z, "")
    try:
        data = json.load(open(server.get_config_dir(INFO_PATH)))
    except:
        data = {}
    try:
        undo = json.load(open(server.get_config_dir(UNDO_PATH)))
    except:
        undo = {}
    user = msg.address.nick
    luser = server.lower(user)
    protected = isprotected(server, user)
    registered = server.registered.get(luser, False)

    if protected and not registered:
        yield (
            "│ This nickname is protected by the owner. "
            "Please identify with NickServ to update your info."
        )
        return

    if luser not in undo or luser not in data:
        yield "│ I have no history recorded for your username."
        return
    undo[luser], data[luser] = data[luser], undo[luser]

    if not data[luser]:
        yield "│ Your information has been deleted."
    else:
        yield "│ Your information has been reverted."

    if registered:
        set_protected(server, user)

    json.dump(data, open(server.get_config_dir(INFO_PATH), "w"))
    json.dump(undo, open(server.get_config_dir(UNDO_PATH), "w"))


__callbacks__ = {"privmsg": [getinfo, setinfo, toggle_protection, undoinfo], "318": [finish_whois]}


def __initialise__(server):
    server.whois_waiting = {}
