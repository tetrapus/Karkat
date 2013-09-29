import os

import yaml

from irc import Message

REPLYFILE = "ctcp.yaml"

def __initialise__(name, bot, stream):
	replies = {}
	if os.path.exists(REPLYFILE):
		replies.update(yaml.safe_load(open(REPLYFILE)))
	conf = bot.get_config_dir(REPLYFILE)
	if os.path.exists(conf):
		replies.update(yaml.safe_load(open(conf)))

	if replies:
		replies = {key.upper(): value for key, value in replies.items()}

		def ctcpreply(line):
			msg = Message(line)
			text = msg.text
			if len(text) > 1 and text[0] == text[-1] == "\x01":
				text = text[1:-1].split(" ")
				command = text[0].upper()
				if command in replies:
					stream.raw_message("NOTICE %s :\x01%s %s\x01" % (msg.context, command, replies[command].format(*text)))

		bot.register("privmsg", ctcpreply)
	else:
		print("%s: Warning: No config files found. CTCP response module not loaded." % __name__)