from django.db import models


class Node(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Edge(models.Model):
    source = models.ForeignKey(Node, related_name="outgoing_edges", on_delete=models.CASCADE)
    destination = models.ForeignKey(Node, related_name="incoming_edges", on_delete=models.CASCADE)
    latency = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "destination"],
                name="unique_edge_source_destination",
            )
        ]
        ordering = ["source__name", "destination__name"]

    def __str__(self):
        return f"{self.source} -> {self.destination} ({self.latency})"


class RouteHistory(models.Model):
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    total_latency = models.FloatField()
    path = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source} -> {self.destination} at {self.created_at:%Y-%m-%d %H:%M:%S}"
