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
    ) -> Optional[Route]:
        """Find the optimal route from source format to target format."""
        if source == target:
            return Route(source=source, target=target, edges=[], total_cost=0)

        # Priority queue stores tuples: (cumulative_cost, node, edge_sequence)
        # Using counter to avoid edge comparison when costs match
        counter = 0
        queue: List[Tuple[int, int, str, List[Edge]]] = [(0, counter, source, [])]
        visited_costs: Dict[str, int] = {}

        while queue:
            cost, _, current, path = heapq.heappop(queue)

            if current in visited_costs and visited_costs[current] <= cost:
                continue
            visited_costs[current] = cost

            if current == target:
                return Route(
                    source=source,
                    target=target,
                    edges=path,
                    total_cost=cost,
                )

            for edge in self._adjacency.get(current, []):
                # Filter out unavailable tools if required
                if require_available and not edge.check_available():
                    continue

                # Filter by forced engine for single-step conversions if specified
                if forced_engine and len(path) == 0 and edge.engine_name != forced_engine:
                    continue

                # Prevent cycles in route
                if edge.target in [e.source for e in path] or edge.target == source:
                    continue

                next_cost = cost + edge.cost
                if edge.target in visited_costs and visited_costs[edge.target] <= next_cost:
                    continue

                counter += 1
                heapq.heappop
                heapq.heappush(
                    queue,
                    (next_cost, counter, edge.target, path + [edge]),
                )

        return None
