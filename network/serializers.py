from rest_framework import serializers

from .models import Edge, Node, RouteHistory


class NodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Node
        fields = ["id", "name"]


class NodeCreateSerializer(serializers.Serializer):
    name = serializers.CharField()


class EdgeSerializer(serializers.ModelSerializer):
    source = serializers.CharField(source="source.name", read_only=True)
    destination = serializers.CharField(source="destination.name", read_only=True)

    class Meta:
        model = Edge
        fields = ["id", "source", "destination", "latency"]


class EdgeCreateSerializer(serializers.Serializer):
    source = serializers.CharField()
    destination = serializers.CharField()
    latency = serializers.FloatField()


class ShortestRouteRequestSerializer(serializers.Serializer):
    source = serializers.CharField()
    destination = serializers.CharField()


class ShortestRouteResponseSerializer(serializers.Serializer):
    total_latency = serializers.FloatField()
    path = serializers.ListField(child=serializers.CharField())


class ErrorSerializer(serializers.Serializer):
    error = serializers.CharField()


class RouteHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteHistory
        fields = ["id", "source", "destination", "total_latency", "path", "created_at"]
