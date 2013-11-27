def set_botmode(server, line):
	server.printer.raw_message("MODE %s +B" % server.nick)
__callbacks__ = {"376": [set_botmode]}