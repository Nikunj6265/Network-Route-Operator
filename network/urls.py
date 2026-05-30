from django.urls import path

from . import views

urlpatterns = [
    path("nodes", views.nodes, name="nodes"),
    path("nodes/<int:node_id>", views.node_detail, name="node-detail"),
    path("edges", views.edges, name="edges"),
    path("edges/<int:edge_id>", views.edge_detail, name="edge-detail"),
    path("routes/shortest", views.shortest_route, name="shortest-route"),
    path("routes/history", views.route_history, name="route-history"),
]
