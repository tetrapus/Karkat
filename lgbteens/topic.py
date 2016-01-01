from bot.events import command

import re
import json
import time
import fnmatch

from util.text import minify, ircstrip

topiclog = "lgbteens-topic.json"

@command("topicban", "(.+)?", prefixes=(".", "@"))
def bans(server, message, mask):
    user = message.address
    if "#lgbteam" not in server.channels or user.nick not in server.channels["#lgbteam"]:
        return "This is a privileged command. Please check your privilege and report any discrepancies to Lion."
    log = getlog()
    if mask:
        if "!" not in mask:
            mask += "!*"
        if "@" not in mask:
            mask += "@*"
        log["banned"].append(mask)
        server.message("%s banned %s from altering the topic." % (user.nick, mask), "#lgbteam")
        savelog(log)
        return "Banned " + mask
    else:
        return ", ".join(log["banned"])

@command("topicunban", "(.+)", prefixes=(".", "@"))
def unban(server, message, mask):
    user = message.address
    if "#lgbteam" not in server.channels or user.nick not in server.channels["#lgbteam"]:
        return "This is a privileged command. Please check your privilege and report any discrepancies to Lion."
    log = getlog()
    if "!" not in mask:
        mask += "!*"
    if "@" not in mask:
        mask += "@*"
    if mask in log["banned"]:
        log["banned"].remove(mask)
        savelog(log)
        server.message("%s removed topic ban on %s." % (user.nick, mask), "#lgbteam")
        return "Allowing %s to alter the topic." % mask
    else:
        return "%s does not match any bans." % mask


@command("topic prepend", "(.+)", prefixes=(".", ""))
def topic(server, message, topic):
    if not server.eq(message.context, "#lgbteens"):
        return
    log = getlog()
    user = message.address
    # Ban check
    if any(fnmatch.fnmatch(user.hostmask.strip(":"), i) for i in log["banned"]):
        return "Sorry, you're not allowed to alter the topic."
    if "#lgbteam" not in server.channels or user.nick not in server.channels["#lgbteam"]:

        # Global time check
        for i in log["log"]:
            if 0 < time.time() - log["log"][i] < 300:
                return "Please don't change the topic too often. Give it time to rest."
        # User time check
        if user.mask in log["log"] and time.time() - log["log"][user.mask] < 3600:
            return "Please don't change the topic too often. Give it time to rest."

    log["log"][user.mask] = time.time()
    topics = [i.strip() for i in log["topic"].split(" | ")]
    newtopic = topic
    if ircstrip(newtopic) != newtopic:
        newtopic = minify(newtopic)+ "\x0f"

    if re.search(r"(the game|a+yy+|^<%(nick)s>|^\* %(nick)s)" % {"nick":re.escape(user.nick.lower())}, ircstrip(newtopic).lower()):
        log["banned"].append("*!*@" + user.mask)
        server.message("%s has been banned from editing the topic." % user.nick, message.context)
        server.message("%s triggered automatic topic ban." % user.nick, "#lgbteam")
        savelog(log)
        return

    while topics:
        t = "%s | %s" % (newtopic, topics.pop(0))
        if len(t.encode("utf-8", errors="replace")) < int(server.server_settings["TOPICLEN"]):
            newtopic = t
        else:
            break
    server.message(newtopic, "#lgbteens", "TOPIC")
    log["topic"] = newtopic
    savelog(log)


def tracktopic(server, line):
    _, evt, newtopic = line.split(":", 2)
    if evt.strip().split()[-1].lower() != "#lgbteens": return
    log = getlog()
    log["topic"] = newtopic
    savelog(log)

def getlog():
    try:
        with open(topiclog) as topics:
            topic = json.load(topics)
    except:
        topic = {"topic": ".topic to add to the topic. Use responsibly or else.", "log": {}, "banned":[]}
        savelog(topic)
    return topic

def savelog(topic):
    with open(topiclog, "w") as topics:
        print(topic)
        topics.write(json.dumps(topic))

__callbacks__ = {"privmsg": [topic, bans, unban], "332": [tracktopic], "topic": [tracktopic]}