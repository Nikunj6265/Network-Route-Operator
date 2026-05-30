from django.contrib import admin

from .models import Edge, Node, RouteHistory


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "destination", "latency")
    list_filter = ("source", "destination")


@admin.register(RouteHistory)
class RouteHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "destination", "total_latency", "created_at")
    list_filter = ("source", "destination", "created_at")
    readonly_fields = ("created_at",)
