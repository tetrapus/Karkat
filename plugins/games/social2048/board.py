import pprint
import random


class Board(object):

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
        return [self.reduce(i) for i in self.board]

    def right(self):
        return [self.reduce(i[::-1])[::-1] for i in self.board]

    def up(self):
        return [list(x) for x in zip(*[self.reduce(i) for i in zip(*self.board)])]

    def down(self):
        return [list(x) for x in zip(*[self.reduce(i[::-1])[::-1] for i in zip(*self.board)])]

    def move(self, move):
        moves = {"^": self.up, "v": self.down, "<": self.left, ">": self.right}
        board = moves[move]()
        if board == self.board:
            return
        else:
            self.board = board
            self.spawn_tile()
            return self

    def won(self):
        return any(any(i is not None and i >= self.goal for i in rows) for rows in self.board)

    def is_endgame(self):
        # Easy test: Check if any move can be made
        states = self.up(), self.down(), self.left(), self.right()
        return all(self.board == i for i in states) or self.won()

    @staticmethod
    def random_tile():
        return random.choice([2, 2, 2, 2, 2, 2, 2, 2, 2, 4])

    @staticmethod
    def merge(x1, x2):
        if x1 == x2 and x1 is not None:
            return x1 + x2

    @classmethod
    def reduce(cls, vector):
        # Remove 0s
        length = len(vector)
        v = [i for i in vector if i is not None]
        for i, n in enumerate(v[:-1]):
            merged = cls.merge(v[i], v[i+1])
            if merged is not None:
                v[i], v[i+1] = merged, None

        v = [i for i in v if i is not None]
        v += [None] * (length - len(v))
        return v

    def __str__(self):
        return pprint.pformat(self.board)

    def __repr__(self):
        return "\n".join(" | ".join(str(i) for i in j) for j in self.board)

class FibBoard(Board):
    fibs = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765]

    def __init__(goal=377, **kwargs):
        kwargs.update({"goal":goal})
        super().__init__(**kwargs)

    @staticmethod
    def random_tile():
        return 1

    @staticmethod
    def merge(*x):
        if all(x) and sum(x) in FibBoard.fibs:
            return sum(x)

class ZeroBoard(Board):
    @staticmethod
    def random_tile():
        return random.choice([2, 2, 2, 2, 2, 2, 2, 2, 4, 0])

class DeterministicBoard(Board):
    def spawn_tile(self):
        # Get empty tiles
        tile = None
        for y, row in enumerate(self.board):
            for x, cell in enumerate(row):
                if cell is None:
                    tile = (x, y)
                    break
            if tile is not None:
                break
        self.board[tile[1]][tile[0]] = 2
        return tile

class Easy2048(Board):

    def __init__(self, size=(4, 4), goal=2048):
        self.board = [[goal/2 for i in range(size[0])] for j in range(size[1])]
        self.size = size
        self.score = 0
        self.goal = goal

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
        return [[self.reduce(i) for i in plane] for plane in self.board]

    def right(self):
        return [[self.reduce(i[::-1])[::-1] for i in plane] for plane in self.board]

    def up(self):
        return [[list(x) for x in zip(*[self.reduce(i) for i in zip(*plane)])] for plane in self.board]

    def down(self):
        return [[list(x) for x in zip(*[self.reduce(i[::-1])[::-1] for i in zip(*plane)])] for plane in self.board]

    def top(self):
        vecs = list(list(zip(*i)) for i in zip(*self.board))
        vecs = [[self.reduce(v) for v in r] for r in vecs]
        return list(zip(*[list(zip(*i)) for i in vecs]))

    def bottom(self):
        vecs = list(list(zip(*i)) for i in zip(*self.board))
        vecs = [[self.reduce(v[::-1])[::-1] for v in r] for r in vecs]
        return list(zip(*[list(zip(*i)) for i in vecs]))

    def move(self, move):
        moves = {"^": self.up, "v": self.down, "<": self.left, ">": self.right, "+": self.top, "-": self.bottom}
        board = moves[move]()
        if board == self.board:
            return
        else:
            self.board = board
            self.spawn_tile()
            return self

    def won(self):
        return any(any(any(i is not None and i >= self.goal for i in rows) for rows in plane) for plane in self.board)

    def is_endgame(self):
        # Easy test: Check if any move can be made
        states = self.up(), self.down(), self.left(), self.right(), self.top(), self.bottom()
        return all(self.board == i for i in states) or self.won()

    def __repr__(self):
        return "\n....................\n".join("\n".join(" | ".join(str(i) for i in j) for j in self.board))

class NegaBoard(Board):
    pass