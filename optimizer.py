"""Exact integer min-cost flow; standard library only, including on s390x."""
from dataclasses import dataclass, asdict
from math import isfinite

@dataclass(frozen=True)
class Request:
    name: str
    quantity: int
    deadline: int
    penalty: float
    minimum: int = 0

@dataclass(frozen=True)
class Offer:
    name: str
    capacity: int
    arrival: int
    unit_cost: float


def solve(requests, offers):
    """Minimize procurement + unmet-demand penalties, with hard minimums.

    Each request can receive from any offer that arrives by its deadline.
    Successive shortest augmenting paths on the residual network give an
    exact integer solution; the shortage source models unfulfilled demand.
    """
    for items in (requests, offers):
        if len({x.name for x in items}) != len(items):
            raise ValueError('Names must be unique within each participant type.')
    for r in requests:
        if any(type(v) is not int or v < 0 for v in (r.quantity, r.deadline, r.minimum)) or r.minimum > r.quantity:
            raise ValueError('Invalid request quantity, deadline, or minimum.')
        if not isfinite(r.penalty) or r.penalty < 0:
            raise ValueError('Penalties must be finite and nonnegative.')
    for o in offers:
        if any(type(v) is not int or v < 0 for v in (o.capacity, o.arrival)) or not isfinite(o.unit_cost) or o.unit_cost < 0:
            raise ValueError('Invalid offer.')
    n = 3 + len(offers) + len(requests)
    source, sink, shortage = 0, 1, 2
    graph = [[] for _ in range(n)]
    def edge(a, b, capacity, cost):
        forward = [b, len(graph[b]), capacity, cost, capacity]
        reverse = [a, len(graph[a]), 0, -cost, 0]
        graph[a].append(forward)
        graph[b].append(reverse)
        return forward
    total = sum(r.quantity for r in requests)
    edge(source, shortage, total, 0)
    arcs, missing = [], []
    for j, o in enumerate(offers):
        edge(source, 3+j, o.capacity, 0)
    for i, r in enumerate(requests):
        node = 3+len(offers)+i
        edge(node, sink, r.quantity, 0)
        missing.append(edge(shortage, node, r.quantity-r.minimum, r.penalty))
        for j, o in enumerate(offers):
            if o.arrival <= r.deadline:
                arcs.append((i, j, edge(3+j, node, min(o.capacity, r.quantity), o.unit_cost)))
    flow = 0
    while flow < total:
        dist, prev = [float('inf')]*n, [None]*n
        dist[source] = 0
        for _ in range(n-1):
            changed = False
            for a in range(n):
                for k, e in enumerate(graph[a]):
                    if e[2] > 0 and dist[e[0]] > dist[a]+e[3]:
                        dist[e[0]], prev[e[0]] = dist[a]+e[3], (a, k)
                        changed = True
            if not changed:
                break
        if prev[sink] is None:
            raise ValueError('No feasible plan meets the hard minimums and deadlines.')
        amount, node = total-flow, sink
        while node != source:
            a, k = prev[node]
            amount = min(amount, graph[a][k][2])
            node = a
        node = sink
        while node != source:
            a, k = prev[node]
            e = graph[a][k]
            e[2] -= amount
            graph[node][e[1]][2] += amount
            node = a
        flow += amount
    shipments = [dict(factory=requests[i].name, supplier=offers[j].name,
                      quantity=e[4]-e[2], arrival=offers[j].arrival,
                      unit_cost=offers[j].unit_cost) for i,j,e in arcs if e[4]-e[2]]
    decisions = [dict(factory=r.name, requested=r.quantity,
                      allocated=r.quantity-(missing[i][4]-missing[i][2]),
                      unmet=missing[i][4]-missing[i][2]) for i,r in enumerate(requests)]
    procurement = sum(s['quantity']*s['unit_cost'] for s in shipments)
    penalty = sum(d['unmet']*r.penalty for d,r in zip(decisions, requests))
    return dict(shipments=shipments, decisions=decisions, procurement=procurement,
                shortage_penalty=penalty, objective=procurement+penalty,
                audit=dict(capacity_satisfied=True, deadlines_satisfied=True,
                           minimums_satisfied=True, method='Integer min-cost flow',
                           shared_requests=[asdict(r) for r in requests],
                           shared_offers=[asdict(o) for o in offers]))


def demo():
    return ([Request('Factory A', 600, 2, 100, 400), Request('Factory B', 500, 4, 25)],
            [Offer('Supplier S', 800, 1, 5), Offer('Supplier T', 300, 3, 12)])
