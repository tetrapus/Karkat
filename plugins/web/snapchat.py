import time
import json

from util.text import pretty_date
from util.services import pysnap, imgur
from bot.events import Callback, command

class Snap(Callback):

    SETTINGS_FILE = "snapchat.json"

    def __init__(self, server):
        self.settingsf = server.get_config_dir(self.SETTINGS_FILE)
        try:
            self.settings = json.load(open(self.settingsf))
        except FileNotFoundError:
            self.settings = {}
        
        self.accounts = {i: pysnap.Snapchat() for i in self.settings}
        for i in self.settings:
            self.accounts[i].login(self.settings[i]["username"], self.settings[i]["password"])

        super().__init__(server)

    def snapsave(self, data):
        # Check if image file.
        if pysnap.is_image(data):
            # Upload to imgur
            response = imgur.upload(data)
            return response["data"]["link"]

    @command("snapassoc", r"([^ ]+)\s+([^ ]+)\s+([^ ]+)", admin=True)
    def associate(self, server, message, channel, username, password):
        # try to login
        res = pysnap.Snapchat()
        if not res.login(username, password):
            return "Could not log in."
        channel = server.lower(channel)
        if channel in self.accounts:
            self.accounts[channel].logout()
        self.accounts[channel] = res
        self.settings[server.lower(channel)] = {"username": username, "password": password, "snaps": {}, "last": time.time()}
        json.dump(self.settings, open(self.settingsf, "w"))
        return "Associated %s with username %s successfully." % (channel, username)

    def newsnaps(self, channel):
        account = self.accounts[channel]

        if channel not in self.accounts or channel not in self.settings:
            return
        self.settings[channel]["last"] = time.time()
        snaps = account.get_snaps(self.settings[channel]["last"])
        for snap in snaps:
            try:
                if snap["id"] in self.settings[channel]["snaps"]:
                    continue
                url = self.snapsave(account.get_blob(snap["id"]))
                self.settings[channel]["snaps"][snap["id"]] = url
                account.mark_viewed(snap["id"])
                yield "08│12 %s via %s (⌚ %s)" % (url, snap["sender"], pretty_date(time.time() - snap["sent"]/1000) if snap["sent"] else "Unknown")
            except:
                pass
        json.dump(self.settings, open(self.settingsf, "w"))

    @command("snaps")
    def getnewsnaps(self, server, message):
        channel = server.lower(message.context)

        yield from self.newsnaps(channel)

    def checksnaps(self, server, line) -> "ALL":
        for channel in self.settings:
            if time.time() - self.settings[channel]["last"] > 60:
                for i in self.newsnaps(channel):
                    server.message(i, channel)

__initialise__ = Snap