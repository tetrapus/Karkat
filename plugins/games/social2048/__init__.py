import json
import time

from math import log

from . import boards

from bot.events import Callback, command


class IRC2048(Callback):
    colors = [15, 14, 7, 4, 5, 8, 9, 3, 11, 10, 12, 2, 6, 13]
    
    boards = {"easy": boards.Easy2048, "fibbonacci": boards.FibBoard, "zero": boards.ZeroBoard, "deterministic": boards.DeterministicBoard, "classic": boards.Board}
    symbols = {'<': '<', '^': '^', 'left': '<', 'u': '^', 't': '+', 'top': '+', 'v': 'v', 'r': '>', '-': '-', 'l': '<', '>': '>', 'right': '>', 'bottom': '-', '+': '+', 'd': 'v', 'up': '^', 'down': 'v', 'b': '-'}

    @classmethod
    def get_board(cls, board):
        bases = []
        for i in board.split(":"):
            bases.append(getattr(boards, i.split(".")[-1]))
        return type(board, tuple(bases[::-1]), {})

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
            yield "".join("│%s│" % ("".join(("\x030,%.2d%s\x0f" % (self.colors[int(log(cell, 2)) - 1], str(cell).center(5))) if cell else {0: "  0  ", None:"     "}[cell] for cell in row)) for row in slice_)

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
                bases.append(self.boards[i.lower().strip()])
        Board = type(":".join(i.__name__ for i in bases), tuple(bases[::-1]), {})
        if server.lower(msg.context) not in self.games:
            self.games[server.lower(msg.context)] = Board(goal=int(msg.command), size=dim)
        board = self.games[server.lower(msg.context)]
        self.savestate()
        yield from self.print_board(board)

    @command("endgame", admin=True)
    def endgame(self, server, msg):
        del self.games[server.lower(msg.context)]

    @command("up down left right top bottom u d l r t b", r"((?:(?:up|down|left|right|top|bottom|[udlrtb^v<>+-])\s*)*)(repeat)?")
    def move(self, server, msg, args, repeat):
        moves = [msg.command]
        if args: 
            moves += args.split()
        seq = "".join(self.symbols[i.lower()] for i in moves)
        yield from self.moves.funct(self, server, msg, seq, repeat)
    
    @command("move", r"([udlrtb^v<>+-]+)(\s+repeat)?")
    def moves(self, server, msg, seq, repeat):
        if server.lower(msg.context) not in self.games:
            self.games[server.lower(msg.context)] = boards.Board()
        board = self.games[server.lower(msg.context)]
        score = board.score
        once = True
        t = time.time()
        while repeat or once:
            if time.time() - t > 5:
                break
            once = False
            for i in seq:
                board.move(self.symbols[i.lower()])
                if board.is_endgame():
                    repeat = False
                    break
            if board.score == score:
                repeat = False
            score = board.score
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