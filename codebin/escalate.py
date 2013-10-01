from irc import Callback

def __initialise__(name, bot, stream):
	cb = Callback()
	cb.initialise(name, bot, stream)
	@cb.command("escalate", "(.+)", help="12Escalate05⎟ Sets temporary admin permissions on your hostmask.\n"
										 "12        05⎟ Usage: [!@]escalate <password>")
	def escalate(message, password):
		if password == 