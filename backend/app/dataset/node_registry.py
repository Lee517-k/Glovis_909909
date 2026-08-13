from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.dataset.loader import Dataset, load_dataset


@dataclass(frozen=True)
class NodeInfo:
    node_id: str
    location_id: str
    node_name: str
    node_type: str | None
    country_code: str | None


class NodeRegistry:
    def __init__(self, dataset: Dataset):
        self._nodes: dict[str, NodeInfo] = {}
        self._by_location: dict[str, set[str]] = {}
        self._index_dataset(dataset)

    def _add(self, ref: dict) -> None:
        node_id = ref.get("node_id")
        if not node_id or node_id in self._nodes:
            return
        location_id = ref.get("location_id", node_id)
        info = NodeInfo(
            node_id=node_id,
            location_id=location_id,
            node_name=ref.get("name", node_id),
            node_type=ref.get("node_type"),
            country_code=ref.get("country") or ref.get("country_code"),
        )
        self._nodes[node_id] = info
        self._by_location.setdefault(location_id, set()).add(node_id)

    def _index_dataset(self, dataset: Dataset) -> None:
        for group in (dataset.sea, dataset.rail, dataset.road, dataset.air):
            for carrier in group:
                for service in carrier.services:
                    self._add(service["origin"])
                    self._add(service["destination"])

        for port in dataset.ports:
            self._add(
                {
                    "node_id": port.get("node_id", port["port_id"]),
                    "name": port["port_name"],
                    "node_type": port.get("node_type", "seaport"),
                    "location_id": port.get("location_id", port["port_id"]),
                    "country": port.get("country_code"),
                }
            )

        for corridor in dataset.road_corridors:
            self._add(corridor["origin"])
            self._add(corridor["destination"])

    def get(self, node_id: str) -> NodeInfo | None:
        return self._nodes.get(node_id)

    def all_nodes(self) -> list[NodeInfo]:
        return list(self._nodes.values())

    def location_of(self, node_id: str) -> str | None:
        info = self.get(node_id)
        return info.location_id if info else None

    def same_location(self, node_id_a: str, node_id_b: str) -> bool:
        loc_a = self.location_of(node_id_a)
        loc_b = self.location_of(node_id_b)
        return loc_a is not None and loc_a == loc_b

    def nodes_at_location(self, location_id: str) -> set[str]:
        return self._by_location.get(location_id, set())


@lru_cache(maxsize=1)
def get_node_registry() -> NodeRegistry:
    return NodeRegistry(load_dataset())


def reset_cache() -> None:
    get_node_registry.cache_clear()
