from bot.events import Callback, msghandler, command
from util import database, files
import re
import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, DateTime, Text, Index, desc
from sqlalchemy.sql import func

Base = declarative_base()

class KarmaLog(Base):
    __tablename__ = "karma"
    id = Column(Integer, primary_key=True)

    timestamp = Column(DateTime, nullable=False)

    giver = Column(Text)
    giver_lower = Column(Text)

    receiver = Column(Text)
    receiver_raw = Column(Text)

    value = Column(Integer, nullable=False)


class Karma(Callback):

    def __init__(self, server):
        self.karmapath = server.get_config_dir("karma.db")
        self.db = database.Database("sqlite:///" + self.karmapath)
        self.db.create_all(Base.metadata)
        self.settingspath = server.get_config_dir("karma-settings.json")
        self.settings = files.Config(self.settingspath)
        self.RE_NICK = r"[a-z_\-\[\]\\^{}|`][a-z0-9_\-\[\]\\^{}|`]{1,%d}" % (
            int(server.server_settings.get("NICKLEN", 9))-1
        )
        self.RE_PLUS = r"^(?:\+\+({0})|({0})\+\+|\+1\s+({0}))".format(
            self.RE_NICK
        )
        self.RE_MINUS = r"^(?:\-\-({0})|({0})\-\-|\-1\s+({0}))".format(
            self.RE_NICK
        )
        super().__init__(server)

    def get_karma(self, session, user):
        return session.query(
            func.sum(KarmaLog.value)
        ).filter(
            KarmaLog.receiver == user,
            KarmaLog.giver_lower != user
        ).first()[0] or 0

    def get_self_karma(self, session, user):
        return session.query(
            func.sum(KarmaLog.value)
        ).filter(
            KarmaLog.receiver == user,
            KarmaLog.giver_lower == user,
            KarmaLog.value == 1
        ).first()[0] or 0

    def get_biggest_fan(self, session, user):
        return session.query(
            KarmaLog,
            func.sum(KarmaLog.value).label('karma')
        ).filter(
            KarmaLog.receiver == user
        ).group_by(
            KarmaLog.giver_lower
        ).order_by(desc('karma')).first()

    def get_biggest_hater(self, session, user):
        return session.query(
            KarmaLog,
            func.sum(KarmaLog.value).label('karma')
        ).filter(
            KarmaLog.receiver == user
        ).group_by(
            KarmaLog.giver_lower
        ).order_by('karma').first()

    @msghandler
    def increment(self, server, msg):
        giver = msg.address.nick
        context = server.lower(msg.context)
        text = msg.text.rstrip(";")
        plus_matches = re.match(self.RE_PLUS, text, flags=re.IGNORECASE)
        minus_matches = re.match(self.RE_MINUS, text, flags=re.IGNORECASE)
        if plus_matches:
            user = [i for i in plus_matches.groups() if i is not None][0]
            inc = 1
        elif minus_matches:
            user = [i for i in minus_matches.groups() if i is not None][0]
            inc = -1
        else:
            return

        with self.db() as session:
            log = KarmaLog(
                timestamp=datetime.datetime.utcnow(),
                giver=giver,
                giver_lower=server.lower(giver),
                receiver=server.lower(user),
                receiver_raw=user,
                value=inc
            )
            session.add(log)
            if context in self.settings and not self.settings[context]:
                return
            karma = self.get_karma(session, server.lower(user))
        if server.eq(user, giver):
            karma = karma + inc
        return "07⎟ %s now has %d karma." % (user, karma)

    @command("setkarma", "(on|off)", admin=True)
    def setkarma(self, server, msg, setting):
        if setting == 'on':
            self.settings[server.lower(msg.context)] = True
            return "07⎟ Karma enabled."
        elif setting == 'off':
            self.settings[server.lower(msg.context)] = False
            return "07⎟ Karma disabled."

    @command("karma", r"(\w*)")
    def karma(self, server, msg, user):
        """ Show a user's karma score. """
        if not user:
            user = msg.address.nick
        with self.db() as session:
            key = server.lower(user)
            karma = self.get_karma(session, key)
            self_karma = self.get_self_karma(session, key)
            fan = self.get_biggest_fan(session, key)
            hater = self.get_biggest_hater(session, key)
            karma_shame, biggest_fan, biggest_hater = "", "", ""
            if self_karma:
                karma_shame = " · %d self-karma attempt%s" % (
                    self_karma, 's' if self_karma != 1 else ''
                )
            if fan is not None and fan[1] > 0:
                biggest_fan = " · Biggest fan: %s (%d)" % (fan[0].giver, fan[1])
            if hater is not None and hater[1] < 0:
                biggest_hater = " · Worst critic: %s (%d)" % (
                    hater[0].giver, hater[1]
                )
        return "\x0307⎟\x03 %s \x0307⎟\x03 %s karma%s%s%s" % (
            user, karma, karma_shame, biggest_fan, biggest_hater
        )


__initialise__ = Karma
