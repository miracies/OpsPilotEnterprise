from __future__ import annotations

from pydantic import BaseModel


class TopologyNode(BaseModel):
    id: str
    name: str
    type: str
    status: str | None = None
    metadata: dict = {}


class TopologyEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    metadata: dict = {}


class TopologyGraph(BaseModel):
    graph_id: str
    connection_id: str
    generated_at: str
    nodes: list[TopologyNode] = []
    edges: list[TopologyEdge] = []
    metadata: dict = {}
