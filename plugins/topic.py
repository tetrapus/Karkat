"""
Command for queue-like topic manipulation.
"""

from bot.events import command
from util.text import join_until, encoded_size


@command("topic", "(.+)")
def topic(server, msg, text):
    """ Prepend some text to the topic. """

    context_key = server.lower(msg.context)
    nick = msg.address.nick
    topic_max = int(server.server_settings["TOPICLEN"])

    if server.channel_modes.get(context_key, {}).get('t'):
        # Check user permissions
        if server.rank_to_int('%') > server.numeric_rank(nick, context_key):
            return

    old_topic = server.topic[server.lower(msg.context)]
    if old_topic:
        # Add as many old topics as will fit
        text = join_until(
            " | ",
            old_topic.split(" | "),
            ceiling=topic_max,
            measure=lambda s: encoded_size(server.encoding, s)
        )

    server.printer.message(text, msg.context, "TOPIC")

__callbacks__ = {"privmsg": [topic]}
