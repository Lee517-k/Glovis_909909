from __future__ import annotations

from collections import defaultdict

from app.planning.types import SegmentProposal


class SegmentGraph:
    """Adjacency list of validated SegmentProposal edges, keyed by origin node.

    Built once per planning run from every agent's (already cargo-feasible)
    proposals - the Coordinator's job is only to connect these, never to
    invent a segment itself (spec section 5.3 / section 6).
    """

    def __init__(self, segments: list[SegmentProposal]):
        self._by_origin: dict[str, list[SegmentProposal]] = defaultdict(list)
        for seg in segments:
            self._by_origin[seg.origin_node_id].append(seg)

    def segments_from(self, node_id: str) -> list[SegmentProposal]:
        return self._by_origin.get(node_id, [])

    def has_any_segment_touching(self, node_id: str) -> bool:
        if node_id in self._by_origin:
            return True
        return any(seg.destination_node_id == node_id for segs in self._by_origin.values() for seg in segs)


def build_graph(segments: list[SegmentProposal]) -> SegmentGraph:
    return SegmentGraph(segments)
