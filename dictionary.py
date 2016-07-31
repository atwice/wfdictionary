import bisect

class DicNode:

	EmptyLeaf = 0

	def __init__(self):
		self.keys = []
		self.children = []
		self.data = None

	def next(self, letter):
		i = bisect.bisect_left(self.keys, letter)
		if i < len(self.keys) and self.keys[i] == letter:
			return self.children[i]
		return None

	def add(self, letter):
		i = bisect.bisect_left(self.keys, letter)
		if i >= len(self.keys) or self.keys[i] != letter:
			self.keys.insert(i, letter) 
			self.children.insert(i, DicNode())
		return self.children[i]

	def set_leaf(self, attr):
		if attr is not None:
			self.data = attr
		else:
			self.data = DicNode.EmptyLeaf 

	def is_leaf(self):
		return self.data is not None


####################################################################################################

class DicTree:

	def __init__(self):
		self.root = DicNode()


	def add_word(self, word, attr = DicNode.EmptyLeaf):
		assert word is not None and word != ""
		curr_node = self.root
		for letter in word:
			curr_node = curr_node.add(letter)
		curr_node.set_leaf(attr)


	def check_word(self, word):
		curr_node = self.root

		for letter in word:
			curr_node = curr_node.next(letter)
			if curr_node is None:
				return False

		return curr_node.is_leaf()

####################################################################################################

import unittest

class TestEmptyDictionary(unittest.TestCase):
	def setUp(self):
		self.dictionary = DicTree()

	def test_empty_dictionary(self):
		self.assertFalse(self.dictionary.check_word(""))
		self.assertFalse(self.dictionary.check_word("any word"))
		self.assertFalse(self.dictionary.check_word("a"))
		self.assertFalse(self.dictionary.check_word(" "))

class TestDictionary(unittest.TestCase):

	def test_one_word(self):
		dic = DicTree()
		self.assertFalse(dic.check_word("hello"))
		dic.add_word("hello")
		self.assertTrue(dic.check_word("hello"))

	def test_multi_word(self):
		dic = DicTree()
		dic.add_word("anyone")
		dic.add_word("anywhere")
		dic.add_word("any")
		dic.add_word("someone")
		dic.add_word("somewhere")
		self.assertTrue(dic.check_word("anyone"))
		self.assertTrue(dic.check_word("anywhere"))
		self.assertTrue(dic.check_word("any"))
		self.assertTrue(dic.check_word("someone"))
		self.assertTrue(dic.check_word("somewhere"))
		self.assertFalse(dic.check_word("some"))
		self.assertFalse(dic.check_word("a"))
		self.assertFalse(dic.check_word("an"))
		self.assertFalse(dic.check_word("anyo"))
		self.assertFalse(dic.check_word("anyon"))

if __name__ == "__main__":
	unittest.main()
