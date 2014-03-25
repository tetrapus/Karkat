import json

from math import log

from . import boards

from bot.events import Callback, command


class IRC2048(Callback):
    colors = [15, 14, 7, 4, 5, 8, 9, 3, 11, 10, 12, 2, 6, 13]
    
    boards = {"easy": boards.Easy2048, "fibbonacci": boards.FibBoard, "zero": boards.ZeroBoard, "deterministic": boards.DeterministicBoard, "classic": boards.Board}

    @classmethod
    def get_board(cls, board):
        bases = []
        for i in board.split(":"):
            bases.append(getattr(boards, i.split(".")[-1]))
        return type(board, tuple(bases), {})

    def __init__(self, server):
        self.savefile = server.get_config_dir("2048.json")
        try:
            self.games = json.load(open(self.savefile))
            for chan, game in self.games.items():
                self.games[chan] = self.get_board(game["type"]).unserialise(game)
        except FileNotFoundError:
            self.games = {}
        super().__init__(server)

    def print_board(self, board):
        if len(board.size) == 2:
            b = [board.board]
        else:
            b = board.board
        board = zip(*b)
        for y, slice_ in enumerate(board):
            yield " ".join("│%s│" % ("│".join(("\x030,%.2d%s\x0f" % (self.colors[int(log(cell, 2)) - 1], str(cell).center(4))) if cell else {0: " 0  ", None:"    "}[cell] for cell in row)) for row in slice_)

    @command("4096 2048 1024 512 256 128 64 32 16 8 13 21 34 55 89 144 233 377 610 987 1597 2584 4181 6765", r"((?:(?:easy|fibbonacci|zero|deterministic)\s*)+)?(\d+x\d+(?:x\d+)?)?")
    def start(self, server, msg, typ, dim):
        dim = dim or "4x4"
        dim = tuple(min(int(i), 5) for i in dim.split("x"))
        if len(dim) == 3:
            bases = [boards.Board3D]
        else:
            bases = [boards.Board]
        if int(msg.command) in [13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765]:
            bases.append(boards.FibBoard)
        if typ:
            for i in typ.split():
                bases.append(self.boards[typ.lower().strip()])
        Board = type(":".join(i.__name__ for i in bases), tuple(bases), {})
        if server.lower(msg.context) not in self.games:
            self.games[server.lower(msg.context)] = Board(goal=int(msg.command), size=dim)
        board = self.games[server.lower(msg.context)]
        self.savestate()
        yield from self.print_board(board)

    @command("endgame", admin=True)
    def endgame(self, server, msg):
        del self.games[server.lower(msg.context)]

    @command("up down left right top bottom u d l r t b", r"((?:(?:up|down|left|right|top|bottom|u|d|l|r|t|b)\s*)*)")
    def move(self, server, msg, args):
        moves = [msg.command]
        if args: 
            moves += args.split()
        if server.lower(msg.context) not in self.games:
            self.games[server.lower(msg.context)] = boards.Board()
        board = self.games[server.lower(msg.context)]
        for i in moves:
            board.move({"up":"^", "down":"v", "left":"<", "right":">", "u":"^", "d":"v", "l":"<", "r":">", "top":"+", "bottom": "-", "t": "+", "b":"-"}[i.lower()])
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
        self.savestate()
        yield from self.print_board(board)
    
    @command("move", "([udlrtb]+)")
    def moves(self, server, msg, seq):
        if server.lower(msg.context) not in self.games:
            self.games[server.lower(msg.context)] = boards.Board()
        board = self.games[server.lower(msg.context)]
        for i in seq:
            board.move({"u":"^", "d":"v", "l":"<", "r":">", "t": "+", "b":"-"}[i.lower()])
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
        self.savestate()
        yield from self.print_board(board)


    def savestate(self):
        with open(self.savefile, "w") as f:
            json.dump({k: v.serialise() for k, v in self.games.items()}, f)

__initialise__ = IRC2048