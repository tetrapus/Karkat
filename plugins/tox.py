import json

from bot.events import Callback, command

class Tox(Callback):
    USERS = "tox.json"

    def __init__(self, server):
        self.ufile = server.get_config_dir(self.USERS)
        try:
            with open(self.ufile) as f:
                self.users = json.load(f)
        except:
            self.users = {}
        super().__init__(server)

    @command("tox", "(\S+)")
    def tox(self, server, message, user):
        if server.lower(user) in self.users:
            return "11│ %s 11│ %s" % (user, self.users[server.lower(user)])
        return "11│ 🔒 │ %s has no associated tox ID." % (user)

    @command("settox", "([A-F0-9]{76})", templates={Callback.USAGE: "04│ 🔒 │ Please supply a valid public key."})
    def settox(self, server, message, token):
        self.users[server.lower(message.address.nick)] = token
        self.save()
        return "11│ 🔒 │ %s associated with %s." % (message.address.nick, token[:4] + "\x0315..\x0f" + token[-4:])

    def save(self):
        with open(self.ufile, "w") as f:
            json.dump(self.users, f)

__initialise__ = Tox