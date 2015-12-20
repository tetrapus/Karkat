from bot.events import Callback, msghandler
from util import database
import re
import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, DateTime, Text, Index
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
        self.db = database.Database("sqlite://" + self.karmapath)
        self.db.create_all(Base.metadata)
        self.nickre = re.compile(r"[a-z_\-\[\]\\^{}|`][a-z0-9_\-\[\]\\^{}|`]{2,%d}" % (int(server.get("NICKLEN", 9))-1))
        super().__init__(server)

    def get_karma(self, user):
        with self.db() as session:
            return session.query(
                func.sum(KarmaLog.value)
            ).filter(
                KarmaLog.receiver == user
            ).first() or 0

    @msghandler
    def increment(self, server, msg):
        giver = msg.address.nick
        text = msg.text.rstrip(";")
        if " " not in text:
            if text.endswith("++"):
                user, inc = text[:-2], 1
            elif text.startswith("++"):
                user, inc = text[2:], 1
            elif text.endswith("--"):
                user, inc = text[:-2], -1
            elif text.startswith("--"):
                user, inc = text[2:], -1
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
            return "07⎟ %s now has %d karma." % self.get_karma(server.lower(user))