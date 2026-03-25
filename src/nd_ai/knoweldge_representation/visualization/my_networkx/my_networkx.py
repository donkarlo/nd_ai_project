import networkx as nx
import matplotlib.pyplot as plt


class MyNetworkx:
    def __init__(self):
        self._graph = nx.Graph()
        self._graph.add_node(1)
        self._graph.add_nodes_from([2, 3])
        self._graph.add_nodes_from([
            (4, {"color": "red"}),
            (5, {"color": "green"}),
        ])
        self._graph.add_edge(1, 2)

    @property
    def graph(self) -> nx.Graph:
        return self._graph

    def show(self) -> None:
        graph = self._graph

        node_colors = []
        for node in graph.nodes:
            node_colors.append(graph.nodes[node].get("color", "lightblue"))

        position = nx.spring_layout(graph, seed=42)

        nx.draw(
            graph,
            pos=position,
            with_labels=True,
            node_color=node_colors,
            node_size=900,
            font_size=12,
        )

        plt.show()


if __name__ == '__main__':
    networkx_obj = MyNetworkx()
    networkx_obj.show()