import npap
import networkx as nx

# Create a graph programmatically
G = nx.DiGraph()

# Add nodes with geographic coordinates
G.add_node("bus_1", lat=47.0, lon=15.0, load=100.0)
G.add_node("bus_2", lat=47.1, lon=15.1, load=150.0)
G.add_node("bus_3", lat=47.2, lon=15.0, load=200.0)
G.add_node("bus_4", lat=47.0, lon=15.2, load=120.0)

# Add edges with electrical properties
G.add_edge("bus_1", "bus_2", x=0.01, p_max=500)
G.add_edge("bus_2", "bus_3", x=0.02, p_max=400)
G.add_edge("bus_3", "bus_4", x=0.015, p_max=450)
G.add_edge("bus_4", "bus_1", x=0.018, p_max=300)

# Initialize manager and load
manager = npap.PartitionAggregatorManager()
manager.load_data("networkx_direct", graph=G)

# Partition
partition = manager.partition("geographical_kmeans", n_clusters=2)

# Aggregate
aggregated = manager.aggregate(mode=npap.AggregationMode.GEOGRAPHICAL)

# Visualize
manager.plot_network(style="voltage_aware")