import pprint
import random
import math

class Board(object):
    """
    Represents a game of 2048.
    """

    newtiles = [2, 2, 2, 2, 2, 2, 2, 2, 2, 4]

    def __init__(self, size=(4, 4), goal=2048, tiles=None, score=0):
        self.size = size
        self.score = 0
        self.goal = goal
        if tiles is None:
            self.board = [[None for i in range(size[0])] for j in range(size[1])]
            self.spawn_tile()
            self.spawn_tile()
        else:
            self.board = tiles
        self.moves = {"^": self.up, "v": self.down, "<": self.left, ">": self.right}


    @classmethod
    def unserialise(cls, js):
        return cls(size=tuple(js["size"]), goal=js["goal"], score=js["score"], tiles=js["tiles"])

    def serialise(self):
        return {"type": self.__class__.__name__,
                "size": self.size,
                "goal": self.goal,
                "score": self.score,
                "tiles": self.board}      

    def spawn_tile(self):
        # Get empty tiles
        empty = []
        for i in range(self.size[0]):
            for j in range(self.size[1]):
                if self.board[j][i] is None:
                    empty.append((i, j))
        spawn = random.choice(empty)
        self.board[spawn[1]][spawn[0]] = self.random_tile()
        return spawn

    def left(self):
        acc = []
        return [self.reduce(i, acc) for i in self.board], acc

    def right(self):
        acc = []
        return [self.reduce(i[::-1], acc)[::-1] for i in self.board], acc

    def up(self):
        acc = []
        return [list(x) for x in zip(*[self.reduce(i, acc) for i in zip(*self.board)])], acc

    def down(self):
        acc = []
        return [list(x) for x in zip(*[self.reduce(i[::-1], acc)[::-1] for i in zip(*self.board)])], acc

    def move(self, move):
        board, score = self.moves[move]()
        if score == 0:
            return
        else:
            self.score += sum(score)
            self.board = board
            self.spawn_tile()
            return self

    def won(self):
        return any(any(i is not None and i >= self.goal for i in rows) for rows in self.board)

    def is_endgame(self):
        # Easy test: Check if any move can be made
        states = [i() for i in self.moves.keys()]
        return all(i[1] == 0 for i in states) or self.won()

    def random_tile(self):
        return random.choice(self.newtiles)

    def merge(self, x1, x2):
        if x1 is not None and x2 is not None and x1 == x2:
            return x1 + x2

    def reduce(self, vector, acc=None):
        score = 0
        length = len(vector)
        v = [i for i in vector if i is not None]
        for i, n in enumerate(v[:-1]):
            merged = self.merge(v[i], v[i+1])
            if merged is not None:
                v[i], v[i+1] = merged, None
                score += merged

        v = [i for i in v if i is not None]
        v += [None] * (length - len(v))
        if acc is not None: 
            acc.append(score)
        return v

    def __str__(self):
        return pprint.pformat(self.board)

    def __repr__(self):
        return "\n".join(" | ".join(str(i) for i in j) for j in self.board)

class FibBoard:
    fibs = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765]

    def merge(self, x1, x2):
        if x1 is not None and x2 is not None and x1 + x2 in self.fibs:
            return x1 + x2

    def random_tile(self):
        return int(super().random_tile() / 2)

class ZeroBoard:
    def random_tile(self):
        if random.random() > 0.9:
            return 0
        else:
            return super().random_tile()

class DeterministicBoard:
    def spawn_tile(self):
        # Get empty tiles
        tile = None
        if len(self.size) == 2:
            boards = [self.board]
        else:
            boards = self.board
        for z, board in enumerate(boards):
            for y, row in enumerate(board):
                for x, cell in enumerate(row):
                    if cell is None:
                        tile = (x, y, z)
                        break
                if tile is not None:
                    break
            if tile is not None:
                break
        boards[tile[2]][tile[1]][tile[0]] = 1
        return tile

class Easy2048:
    def __init__(self, size=(3, 3, 3), goal=2048, tiles=None, score=0):
        self.size = size
        self.score = 0
        self.goal = goal
        if tiles is None:
            self.board = [[int(goal/2) for i in range(size[0])] for j in range(size[1])]
        else:
            self.board = tiles

class Board3D(Board):

    def __init__(self, size=(3, 3, 3), goal=2048, tiles=None, score=0):
        self.size = size
        self.score = 0
        self.goal = goal
        if tiles is None:
            self.board = [[[None for i in range(size[0])] for j in range(size[1])] for k in range(size[2])]
            self.spawn_tile()
            self.spawn_tile()
        else:
            self.board = tiles
        self.moves = {"^": self.up, "v": self.down, "<": self.left, ">": self.right, "+": self.top, "-": self.bottom}


    def spawn_tile(self):
        # Get empty tiles
        empty = []
        for i in range(self.size[0]):
            for j in range(self.size[1]):
                for k in range(self.size[2]):
                    if self.board[k][j][i] is None:
                        empty.append((i, j, k))
        spawn = random.choice(empty)
        self.board[spawn[2]][spawn[1]][spawn[0]] = self.random_tile()
        return spawn

    def left(self):
        acc = []
        return [[self.reduce(i, acc) for i in plane] for plane in self.board], acc

    def right(self):
        acc = []
        return [[self.reduce(i[::-1], acc)[::-1] for i in plane] for plane in self.board], acc

    def up(self):
        acc = []
        return [[list(x) for x in zip(*[self.reduce(i, acc) for i in zip(*plane)])] for plane in self.board], acc

    def down(self):
        acc = []
        return [[list(x) for x in zip(*[self.reduce(i[::-1], acc)[::-1] for i in zip(*plane)])] for plane in self.board], acc

    def top(self):
        acc = []
        vecs = list(list(zip(*i)) for i in zip(*self.board))
        vecs = [[self.reduce(v, acc) for v in r] for r in vecs]
        vecs = list(zip(*[list(zip(*i)) for i in vecs]))
        return [[list(y) for y in x] for x in vecs], acc

    def bottom(self):
        acc = []
        vecs = list(list(zip(*i)) for i in zip(*self.board))
        vecs = [[self.reduce(v[::-1], acc)[::-1] for v in r] for r in vecs]
        vecs = list(zip(*[list(zip(*i)) for i in vecs]))
        return [[list(y) for y in x] for x in vecs], acc

    def won(self):
        return any(any(any(i is not None and i >= self.goal for i in rows) for rows in plane) for plane in self.board)

    def __repr__(self):
        return "\n....................\n".join("\n".join(" | ".join(str(i) for i in j) for j in self.board))

class NegaBoard(Board):
    pass