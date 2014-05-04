from bot.events import command


@command("topic", "(.+)", rank="%")
def topic(server, msg, topic):
    topics = server.topic[server.lower(msg.context)].split(" | ")
    while topics:
        t = "%s | %s" % (topic, topics.pop(0))
        if len(t.encode("utf-8", errors="replace")) < int(server.server_settings["TOPICLEN"]):
            topic = t
        else:
            break
    server.printer.message(topic, msg.context, "TOPIC")

__callbacks__ = {"privmsg":[topic]}