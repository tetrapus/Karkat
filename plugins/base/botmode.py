def __initialise__(name, bot, stream):
	def set_botmode(line):
		stream.raw_message("MODE %s +B" % bot.nick)
	bot.register("376", set_botmode)