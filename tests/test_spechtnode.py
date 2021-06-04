import unittest

from SpchtDescriptorFormat import SpchtNode, SpchtNodeIterator


class TestSpchtNode(unittest.TestCase):

    def test_set_key(self):
        Node = SpchtNode()
        Node['name'] = "Hans"
        self.assertEqual("Hans", Node['name'])

    def test_set_forbidden_key(self):
        Node = SpchtNode()
        with self.assertRaises(KeyError):
            Node['blafasel'] = "neun"

    def test_nonset_key(self):
        Node = SpchtNode()
        self.assertEqual(None, Node.get("mapping"))

    def test_nonset_wrong_key(self):
        Node = SpchtNode()
        self.assertEqual(None, Node.get('key that does not exits at possibility'))

    def test_set_source(self):
        Node = SpchtNode()
        Node['source'] = "marc"
        self.assertEqual("marc", Node['source'])

    def test_set_wrong_source(self):
        Node = SpchtNode()
        Node['source'] = "theuniverseandeverything"
        # defaults to dict
        self.assertEqual("dict", Node['source'])


    def test_set_type(self):
        Node = SpchtNode()
        Node['type'] = "triple"
        self.assertEqual("triple", Node['type'])

    def test_set_wrong_type(self):
        Node = SpchtNode()
        Node['type'] = "type that doesnt exists"
        # type defaults to literal
        self.assertEqual("literal", Node['type'])

    def test_set_requiered(self):
        Node = SpchtNode()
        Node['required'] = "mandatory"
        self.assertEqual("mandatory", Node['required'])

    def test_set_wrong_required(self):
        Node = SpchtNode()
        Node['required'] = "why ever a binary decision is a string"
        self.assertEqual("optional", Node['required'])

    def test_fallback_set(self):
        Node = SpchtNode()
        Node2 = SpchtNode()
        Node['fallback'] = Node2
        self.assertEqual(Node2, Node['fallback'])

    def test_fallback_set_properties(self):
        Node = SpchtNode()
        Node['name'] = "Node1"
        Node2 = SpchtNode()
        Node2['name'] = "Node2"
        Node['fallback'] = Node2
        self.assertEqual("Node2", Node['fallback']['name'])

    def test_fallback_set_to_self(self):
        Node = SpchtNode()
        with self.assertRaises(AttributeError):
            Node['fallback'] = Node

    def test_fallback_set_to_self_tricky(self):
        Node = SpchtNode()
        Node2 = SpchtNode()
        Node2['fallback'] = Node
        with self.assertRaises(AttributeError):
            Node['fallback'] = Node2

    # ! more tests here

    def test_set_map(self):
        Node = SpchtNode()
        Node['mapping'] = {"one": "two"}
        self.assertEqual({"one": "two"}, Node['mapping'])

    def test_set_wrong_map_type(self):
        Node = SpchtNode()
        Node['mapping'] = {"one": "two"}
        Node['mapping'] = "fasel"
        self.assertEqual(None, Node.get('mapping'))

    def test_set_wrong_map_keys(self):
        Node = SpchtNode()
        Node['mapping'] = {5: "bla"}
        self.assertEqual(None, Node.get('mapping'))

    def test_set_non_string_dict_to_map(self):
        Node = SpchtNode()
        Node['mapping'] = {"bla": True}
        self.assertEqual(None, Node.get('mapping'))


if __name__ == '__main__':
    unittest.main()