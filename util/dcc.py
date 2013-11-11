import threading, socket, sys

class PasteListener(threading.Thread):
    def __init__(self, port):
        self.port = port
        threading.Thread.__init__(self)

    def run(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("", self.port))
        self.socket.listen(1)
        print >> sys.__stdout__, "Listening."
        sock, client = self.socket.accept()
        print >> sys.__stdout__, "Connection made."
        paste = ""
        while True:
            data = sock.recv(1024)
            if data:
                paste += data
            else:
                break 
        # code
        try:
            sock.close()
        except:
            pass
        print >> sys.__stdout__, paste
        self.socket.close()