from math import log

from .board import Board

from bot.events import Callback, command

class IRC2048(Callback):
    colors = [15, 14, 7, 8, 4, 5, 8, 9, 3, 11, 10]
    
    def __init__(self, server):
        self.games = {}
        super().__init__(server)

    def print_board(self, board):
        for y, row in enumerate(board.board):
            yield ("\x1f" if y != board.size[1]-1 else "") + "│".join(("\x03%.2d%s\x03" % (self.colors[int(log(cell, 2)) - 1], str(cell).center(4))) if cell else "    " for cell in row) + "\x03"

    @command("2048")
    def start(self, server, msg):
        if server.lower(msg.context) not in self.games:
            self.games[server.lower(msg.context)] = Board()
        board = self.games[server.lower(msg.context)]
        yield from self.print_board(board)

    @command("up down left right")
    def move(self, server, msg):
        if server.lower(msg.context) not in self.games:
            self.games[server.lower(msg.context)] = Board()
        board = self.games[server.lower(msg.context)]
        board.move({"up":"^", "down":"v", "left":"<", "right":">"}[msg.command])
        if board.is_endgame():
            if board.won():
                yield """1413╷ 13╷╭4─╮4╷ 8╷   12╷ 12╷╭13─╮13┌─9╮
144╰┬4╯│8 │8│ 12│   13││13││9 │9│ 11│
148 ╵8 ╰12─╯12╰─13┘   9╰┴9┘╰11─╯11╵ 12╵"""
            else:
                yield """╻  ┏━┓┏━┓┏━━┏┓
┃  ┃ ┃┗━┓┣━ ┣┻┓
┗━━┗━┛┗━┛┗━━╹ ╹"""
            del self.games[server.lower(msg.context)]

        yield from self.print_board(board)

__initialise__ = IRC2048