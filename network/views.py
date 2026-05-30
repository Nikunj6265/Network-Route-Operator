import heapq
from collections import defaultdict
from datetime import datetime, time

from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Edge, Node, RouteHistory
from .serializers import (
    EdgeCreateSerializer,
    EdgeSerializer,
    ErrorSerializer,
    NodeCreateSerializer,
    NodeSerializer,
    RouteHistorySerializer,
    ShortestRouteRequestSerializer,
    ShortestRouteResponseSerializer,
)


def error_response(message, status=400):
    return Response({"error": message}, status=status)


@extend_schema(
    methods=["GET"],
    tags=["Nodes"],
    responses={200: NodeSerializer(many=True)},
    summary="List all nodes",
)
@extend_schema(
    methods=["POST"],
    tags=["Nodes"],
    request=NodeCreateSerializer,
    responses={201: NodeSerializer, 400: ErrorSerializer},
    summary="Create a node",
    examples=[
        OpenApiExample(
            "Create ServerA",
            value={"name": "ServerA"},
            request_only=True,
        )
    ],
)
@api_view(["GET", "POST"])
def nodes(request):
    if request.method == "GET":
        serializer = NodeSerializer(Node.objects.all(), many=True)
        return Response(serializer.data)

    name = (request.data.get("name") or "").strip()
    if not name:
        return error_response("Missing name")

    if Node.objects.filter(name=name).exists():
        return error_response(f"Node '{name}' already exists")

    node = Node.objects.create(name=name)
    return Response(NodeSerializer(node).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Nodes"],
    responses={204: None, 404: ErrorSerializer},
    summary="Delete a node",
)
@api_view(["DELETE"])
def node_detail(request, node_id):
    deleted, _ = Node.objects.filter(id=node_id).delete()
    if not deleted:
        return error_response("Node not found", status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    methods=["GET"],
    tags=["Edges"],
    responses={200: EdgeSerializer(many=True)},
    summary="List all edges",
)
@extend_schema(
    methods=["POST"],
    tags=["Edges"],
    request=EdgeCreateSerializer,
    responses={201: EdgeSerializer, 400: ErrorSerializer},
    summary="Create an edge",
    examples=[
        OpenApiExample(
            "Connect ServerA to ServerB",
            value={"source": "ServerA", "destination": "ServerB", "latency": 12.5},
            request_only=True,
        )
    ],
)
@api_view(["GET", "POST"])
def edges(request):
    if request.method == "GET":
        edges_qs = Edge.objects.select_related("source", "destination")
        serializer = EdgeSerializer(edges_qs, many=True)
        return Response(serializer.data)

    data = request.data
    missing = [field for field in ("source", "destination", "latency") if field not in data]
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    source_name = str(data["source"]).strip()
    destination_name = str(data["destination"]).strip()
    if not source_name or not destination_name:
        return error_response("Source and destination are required")
    if source_name == destination_name:
        return error_response("Source and destination must be different")

    try:
        latency = float(data["latency"])
    except (TypeError, ValueError):
        return error_response("Latency must be a number")
    if latency <= 0:
        return error_response("Latency must be greater than 0")

    nodes_by_name = Node.objects.in_bulk([source_name, destination_name], field_name="name")
    source = nodes_by_name.get(source_name)
    destination = nodes_by_name.get(destination_name)
    if source is None or destination is None:
        return error_response("Source or destination node does not exist")

    duplicate_exists = Edge.objects.filter(source=source, destination=destination).exists()
    reverse_duplicate_exists = Edge.objects.filter(source=destination, destination=source).exists()
    if duplicate_exists or reverse_duplicate_exists:
        return error_response("Edge already exists")

    edge = Edge.objects.create(source=source, destination=destination, latency=latency)
    return Response(EdgeSerializer(edge).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Edges"],
    responses={204: None, 404: ErrorSerializer},
    summary="Delete an edge",
)
@api_view(["DELETE"])
def edge_detail(request, edge_id):
    deleted, _ = Edge.objects.filter(id=edge_id).delete()
    if not deleted:
        return error_response("Edge not found", status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Routes"],
    request=ShortestRouteRequestSerializer,
    responses={
        200: ShortestRouteResponseSerializer,
        400: ErrorSerializer,
        404: ErrorSerializer,
    },
    summary="Find the shortest route",
    examples=[
        OpenApiExample(
            "Shortest route from ServerA to ServerD",
            value={"source": "ServerA", "destination": "ServerD"},
            request_only=True,
        ),
        OpenApiExample(
            "Path found",
            value={"total_latency": 23.4, "path": ["ServerA", "ServerB", "ServerD"]},
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
@api_view(["POST"])
def shortest_route(request):
    data = request.data
    source_name = (data.get("source") or "").strip()
    destination_name = (data.get("destination") or "").strip()
    if not source_name or not destination_name:
        return error_response("Source and destination are required")

    nodes_by_name = Node.objects.in_bulk([source_name, destination_name], field_name="name")
    if source_name not in nodes_by_name or destination_name not in nodes_by_name:
        return error_response("Invalid or non-existent nodes")

    if source_name == destination_name:
        path = [source_name]
        total_latency = 0.0
    else:
        total_latency, path = dijkstra_shortest_path(source_name, destination_name)
        if path is None:
            return error_response(
                f"No path exists between {source_name} and {destination_name}",
                status=status.HTTP_404_NOT_FOUND,
            )

    RouteHistory.objects.create(
        source=source_name,
        destination=destination_name,
        total_latency=total_latency,
        path=path,
    )
    return Response({"total_latency": total_latency, "path": path})


@extend_schema(
    tags=["Routes"],
    parameters=[
        OpenApiParameter("source", str, OpenApiParameter.QUERY, description="Filter by source node name"),
        OpenApiParameter("destination", str, OpenApiParameter.QUERY, description="Filter by destination node name"),
        OpenApiParameter("limit", int, OpenApiParameter.QUERY, description="Maximum number of records to return"),
        OpenApiParameter("date_from", str, OpenApiParameter.QUERY, description="ISO date or datetime lower bound"),
        OpenApiParameter("date_to", str, OpenApiParameter.QUERY, description="ISO date or datetime upper bound"),
    ],
    responses={200: RouteHistorySerializer(many=True), 400: ErrorSerializer},
    summary="List route query history",
)
@api_view(["GET"])
def route_history(request):
    histories = RouteHistory.objects.all()

    source = request.query_params.get("source")
    destination = request.query_params.get("destination")
    if source:
        histories = histories.filter(source=source)
    if destination:
        histories = histories.filter(destination=destination)

    date_from = parse_date_query(request.query_params.get("date_from"), start=True)
    date_to = parse_date_query(request.query_params.get("date_to"), start=False)
    if date_from == "invalid" or date_to == "invalid":
        return error_response("date_from and date_to must be ISO dates or datetimes")
    if date_from:
        histories = histories.filter(created_at__gte=date_from)
    if date_to:
        histories = histories.filter(created_at__lte=date_to)

    limit = request.query_params.get("limit")
    if limit:
        try:
            limit = int(limit)
        except ValueError:
            return error_response("limit must be a positive integer")
        if limit <= 0:
            return error_response("limit must be a positive integer")
        histories = histories[:limit]

    serializer = RouteHistorySerializer(histories, many=True)
    return Response(serializer.data)


def dijkstra_shortest_path(source_name, destination_name):
    graph = defaultdict(list)
    edges = Edge.objects.select_related("source", "destination")
    for edge in edges:
        graph[edge.source.name].append((edge.destination.name, edge.latency))
        graph[edge.destination.name].append((edge.source.name, edge.latency))

    distances = {source_name: 0.0}
    previous = {}
    queue = [(0.0, source_name)]
    visited = set()

    while queue:
        current_distance, current_node = heapq.heappop(queue)
        if current_node in visited:
            continue
        visited.add(current_node)

        if current_node == destination_name:
            return current_distance, build_path(previous, source_name, destination_name)

        for neighbor, latency in graph[current_node]:
            new_distance = current_distance + latency
            if new_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_distance
                previous[neighbor] = current_node
                heapq.heappush(queue, (new_distance, neighbor))

    return None, None


def build_path(previous, source_name, destination_name):
    path = [destination_name]
    while path[-1] != source_name:
        path.append(previous[path[-1]])
    path.reverse()
    return path


def parse_date_query(value, start):
    if not value:
        return None

    try:
        parsed_date = datetime.strptime(value, "%Y-%m-%d").date()
        parsed = datetime.combine(parsed_date, time.min if start else time.max)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return "invalid"

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed
