import pprint
import random


class Board(object):


    def __init__(self, size=(4, 4)):
        self.board = [[0 for i in range(size[0])] for j in range(size[1])]
        self.size = size
        self.score = 0
        self.spawn_tile()
        self.spawn_tile()

    def spawn_tile(self):
        # Get empty tiles
        empty = []
        for i in range(self.size[0]):
            for j in range(self.size[1]):
                if not self.board[j][i]:
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
        return any(any(i >= 2048 for i in rows) for rows in self.board)

    def is_endgame(self):
        # Easy test: Check if any move can be made
        states = self.up(), self.down(), self.left(), self.right()
        return all(self.board == i for i in states) or self.won()

    @staticmethod
    def random_tile():
        return random.choice([2, 2, 2, 2, 2, 2, 2, 2, 2, 4])

    @staticmethod
    def merge(x1, x2):
        if x1 == x2 and x1:
            return x1 + x2

    @classmethod
    def reduce(cls, vector):
        # Remove 0s
        length = len(vector)
        v = [i for i in vector if i]
        for i, n in enumerate(v[:-1]):
            merged = cls.merge(v[i], v[i+1])
            if merged:
                v[i], v[i+1] = merged, 0

        v = [i for i in v if i]
        v += [0] * (length - len(v))
        return v

    def __str__(self):
        return pprint.pformat(self.board)

    def __repr__(self):
        return "\n".join(" | ".join(str(i) for i in j) for j in self.board)