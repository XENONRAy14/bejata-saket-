import unittest
import networkx as nx
from build import distance, graph


class RouteTests(unittest.TestCase):
    def way(self, **tags):
        return dict(id=1, nodes=[1, 2], coords=[[5, 36.75], [5.001, 36.75]], tags=dict(highway='primary', **tags))

    def test_continuity_and_oneway(self):
        g = graph([self.way(oneway='yes', ref='N24')])
        self.assertEqual(nx.shortest_path(g, 1, 2), [1, 2])
        self.assertFalse(g.has_edge(2, 1))
        self.assertAlmostEqual(g[1][2]['length'], g[1][2]['weight'])

    def test_reverse(self):
        g = graph([self.way(oneway='-1')])
        self.assertTrue(g.has_edge(2, 1))
        self.assertFalse(g.has_edge(1, 2))

    def test_empty_and_access(self):
        self.assertEqual(len(graph([])), 0)
        self.assertEqual(len(graph([self.way(access='private')])), 0)

    def test_unreachable_error(self):
        with self.assertRaises(nx.NetworkXNoPath):
            nx.shortest_path(graph([self.way(oneway='yes')]), 2, 1)

    def test_distance(self):
        self.assertEqual(distance([5, 36], [5, 36]), 0)
        self.assertAlmostEqual(distance([0, 0], [0, 1]), 111195, delta=1)


if __name__ == '__main__':
    unittest.main()
