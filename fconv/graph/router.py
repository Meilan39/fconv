"""Dijkstra routing algorithm across atomic conversion edges."""

import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from fconv.graph.edge import Edge


@dataclass
class Route:
    source: str
    target: str
    edges: List[Edge]
    total_cost: int

    @property
    def steps(self) -> int:
        return len(self.edges)

    @property
    def formats(self) -> List[str]:
        if not self.edges:
            return [self.source]
        seq = [self.source]
        for e in self.edges:
            seq.append(e.target)
        return seq

    def format_summary(self) -> str:
        if not self.edges:
            return f"{self.source} (no conversion required)"
        chain = " -> ".join(self.formats)
        tools = ", ".join(e.engine_name for e in self.edges)
        return f"{chain} [Tools: {tools}, Cost: {self.total_cost}]"


class Router:
    def __init__(self, edges: List[Edge]):
        self.edges = edges
        self._adjacency: Dict[str, List[Edge]] = {}
        for edge in edges:
            self._adjacency.setdefault(edge.source, []).append(edge)

    def find_route(
        self,
        source: str,
        target: str,
        forced_engine: Optional[str] = None,
        require_available: bool = True,
        excluded_edges: Optional[Set[str]] = None,
    ) -> Optional[Route]:
        """Find the optimal route from source format to target format."""
        if source == target:
            return Route(source=source, target=target, edges=[], total_cost=0)

        forced_lower = forced_engine.lower() if forced_engine else None
        avail_cache: Dict[object, bool] = {}

        def _is_available(edge: Edge) -> bool:
            fn = edge.check_available
            if fn not in avail_cache:
                avail_cache[fn] = bool(fn())
            return avail_cache[fn]

        # Priority queue stores tuples:
        # (cumulative_cost, hop_count, fallback_count, counter, node, edge_sequence)
        counter = 0
        queue: List[Tuple[int, int, int, int, str, List[Edge]]] = [
            (0, 0, 0, counter, source, [])
        ]
        visited_best: Dict[str, Tuple[int, int, int]] = {}

        while queue:
            cost, hops, fallbacks, _, current, path = heapq.heappop(queue)
            rank = (cost, hops, fallbacks)

            if current in visited_best and visited_best[current] <= rank:
                continue
            visited_best[current] = rank

            if current == target:
                return Route(
                    source=source,
                    target=target,
                    edges=path,
                    total_cost=cost,
                )

            visited_nodes = {e.source for e in path}
            for edge in self._adjacency.get(current, []):
                if excluded_edges and edge.key in excluded_edges:
                    continue

                if edge.terminal_only and edge.target != target:
                    continue

                if require_available and not _is_available(edge):
                    continue

                if forced_lower and len(path) == 0 and edge.engine_name.lower() != forced_lower:
                    continue

                if edge.target in visited_nodes or edge.target == source:
                    continue

                next_cost = cost + edge.cost
                next_hops = hops + 1
                next_fallbacks = fallbacks + (1 if edge.is_fallback else 0)
                next_rank = (next_cost, next_hops, next_fallbacks)
                if edge.target in visited_best and visited_best[edge.target] <= next_rank:
                    continue

                counter += 1
                heapq.heappush(
                    queue,
                    (next_cost, next_hops, next_fallbacks, counter, edge.target, path + [edge]),
                )

        return None
