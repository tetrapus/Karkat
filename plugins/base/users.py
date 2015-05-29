import json

from bot.events import command, Callback

SETTINGS_FILE = "wolfram_users.json"

PROTECTION_FILE = "users.json"

def __initialise__(server):

    def get_settings():
        try:
            return json.load(open(server.get_config_dir(SETTINGS_FILE)))
        except:
            return {}

    def set_settings(settings):
        json.dump(settings, open(server.get_config_dir(SETTINGS_FILE), "w"))

        # TODO: make atomic

    @command("set", r"(\S+)(?:\s+(.+))?", templates={
                Callback.USAGE:"14⚙ 04⎟ Usage: [.@](set) 03(ip|location) [value]"})
    def update_settings(server, msg, varname, value):
        var = varname.lower()
        nick = server.lower(msg.address.nick) 
        protected = server.is_protected(server, nick)
        registered = server.registered.get(nick, False)
        if protected and not registered:
            return "14⚙ 04⎟ This nickname is protected by the owner. Please identify with NickServ to update your info."
        if varname not in ("location", "ip"):
            return "14⚙ 04⎟ No such setting."

        settings = server.get_settings()

        if value is None:
            try:
                value = repr(settings[nick][var])
            except:
                value = "not set"
            return "14⚙ 05⎟ Your %s is currently %s." % (var, value) 
        else:
            if nick in settings:
                settings[nick][var] = value
            else:
                settings[nick] = {var: value}
            server.set_settings(settings)
            server.set_protected(nick)
            return "14⚙ 05⎟ Your %s has been set to %r." % (var, value)

    def is_protected(user):
        try:
            protected = json.load(open(server.get_config_dir(PROTECTION_FILE)))
        except:
            protected = {}
        return server.lower(user) in protected and protected[server.lower(user)]

    def set_protected(user):
        """ Add protection if not defined """
        try:
            protected = json.load(open(server.get_config_dir(PROTECTION_FILE)))
        except:
            protected = {}
        if server.lower(user) not in protected:
            protected[server.lower(user)] = True
        json.dump(protected, open(server.get_config_dir(PROTECTION_FILE), "w"))

    server.get_settings = get_settings
    server.set_settings = set_settings
    server.set_protected = set_protected
    server.is_protected = is_protected
    server.register("privmsg", update_settings)