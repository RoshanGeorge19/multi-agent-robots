"""A coarse ASCII map of the maze, for an LLM to plan on.

The navigation policies are reactive: they see a lidar scan and a goal bearing,
never a map, so a goal on the far side of a wall looks identical to one in open
space. A map is the one thing a language-level planner can add that the policies
lack -- which is what the coordinator experiment tests.

Free space is taken from the env's validated spawn set (points with wall
clearance), binned onto a grid. Cells with no valid point are drawn as walls.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np


class MazeMap:
    def __init__(self, free_points_xy: np.ndarray, cell: float = 0.1):
        """free_points_xy: (N, 2) env-local points known to be free."""
        self.cell = cell
        self.origin = free_points_xy.min(axis=0) - cell
        extent = free_points_xy.max(axis=0) + cell - self.origin
        self.cols = int(math.ceil(extent[0] / cell))
        self.rows = int(math.ceil(extent[1] / cell))
        self.free = np.zeros((self.rows, self.cols), dtype=bool)
        for row, col in map(self.to_cell, free_points_xy):
            self.free[row, col] = True

    def to_cell(self, xy) -> tuple[int, int]:
        """(row, col) of an env-local point. Row 0 is the top (max y)."""
        col = int((xy[0] - self.origin[0]) / self.cell)
        row = self.rows - 1 - int((xy[1] - self.origin[1]) / self.cell)
        return min(max(row, 0), self.rows - 1), min(max(col, 0), self.cols - 1)

    def to_xy(self, row: int, col: int) -> np.ndarray:
        """Centre of a cell, env-local."""
        x = self.origin[0] + (col + 0.5) * self.cell
        y = self.origin[1] + (self.rows - 1 - row + 0.5) * self.cell
        return np.array([x, y], dtype=np.float32)

    def is_free(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols and bool(self.free[row, col])

    def nearest_free(self, row: int, col: int) -> tuple[int, int]:
        """Snap a cell onto free space -- LLMs are off by one often enough to matter."""
        if self.is_free(row, col):
            return row, col
        rr, cc = np.nonzero(self.free)
        k = int(np.argmin((rr - row) ** 2 + (cc - col) ** 2))
        return int(rr[k]), int(cc[k])

    def path(self, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]] | None:
        """Shortest 8-connected path over free cells (BFS), start and goal included.

        Endpoints are snapped onto free space first: a robot hugging a wall can
        sit in a cell the clearance-based map marks as blocked.
        """
        start, goal = self.nearest_free(*start), self.nearest_free(*goal)
        parent = {start: None}
        queue = deque([start])
        while queue:
            cell = queue.popleft()
            if cell == goal:
                path = []
                while cell is not None:
                    path.append(cell)
                    cell = parent[cell]
                return path[::-1]
            r, c = cell
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nxt = (r + dr, c + dc)
                    # no corner cutting: a diagonal needs both orthogonal cells free
                    if nxt in parent or not self.is_free(*nxt):
                        continue
                    if dr and dc and not (self.is_free(r + dr, c) and self.is_free(r, c + dc)):
                        continue
                    parent[nxt] = cell
                    queue.append(nxt)
        return None

    def path_length_m(self, path: list[tuple[int, int]]) -> float:
        steps = zip(path, path[1:])
        return self.cell * sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in steps)

    def line_of_sight(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        """True if every cell on the straight segment a-b is free."""
        n = max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2 + 1
        for t in np.linspace(0.0, 1.0, n):
            r = int(round(a[0] + t * (b[0] - a[0])))
            c = int(round(a[1] + t * (b[1] - a[1])))
            if not self.is_free(r, c):
                return False
        return True

    def random_free(self, rng: np.random.Generator) -> tuple[int, int]:
        rr, cc = np.nonzero(self.free)
        k = int(rng.integers(len(rr)))
        return int(rr[k]), int(cc[k])

    def render(self, markers: dict[str, tuple[float, float]]) -> str:
        """ASCII grid with single-character markers at env-local positions.

        Later markers overwrite earlier ones on a shared cell, so pass goals
        before robots.
        """
        grid = [["." if f else "#" for f in row] for row in self.free]
        for char, xy in markers.items():
            r, c = self.to_cell(xy)
            grid[r][c] = char
        width = len(str(self.cols - 1))
        header_tens = " " * 4 + "".join(str(c // 10) if c >= 10 else " " for c in range(self.cols))
        header_ones = " " * 4 + "".join(str(c % 10) for c in range(self.cols))
        lines = [header_tens, header_ones] if width > 1 else [header_ones]
        lines += [f"{r:>3} " + "".join(row) for r, row in enumerate(grid)]
        return "\n".join(lines)
