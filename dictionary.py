import bisect

def add_to_hash( hash, to_add ):
	return ( hash << 5 ) + hash + to_add


####################################################################################################

class DicNode:

	NotLeaf = -1
	EmptyLeaf = 0

	def __init__(self):
		self.keys = []
		self.children = []
		self.data = None
		self.hash = None


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


	def __eq__(self, other):
		if len( self.keys ) != len( other.keys ):
			return False
		if self.data != other.data:
			return False
		for i in range( len( self.keys ) ):
			if self.keys[i] != other.keys[i]:
				return False
			if self.children[i] != other.children[i]:
				return False
		return True


	def __hash__(self):
		if self.hash is not None:
			return self.hash

		h = 0
		h = add_to_hash( h, len( self.keys ) )
		h = add_to_hash( h, self.data )
		
		for i in range( len( self.keys ) ):
			h = add_to_hash( h, ord( self.keys[i] ) )
			h = add_to_hash( h, hash( self.children[i] ) )

		self.hash = h
		return self.hash


####################################################################################################

class DicSerializer:

	Magic = b'WFTREE'
	HeaderSize = len( Magic ) + 2

	def __init__(self, v = 0):
		self.init_version( v )
		self.data = bytearray()


	def init_version(self, v):
		self.version = v
		if v == 0:
			self.child_count_bytes = 4
			self.attr_bytes = 4
			self.letter_bytes = 4
			self.offset_bytes = 4
		else:
			raise ValueError( "Unknown DicSerializer version: " + v )

		self.before_table_bytes = self.child_count_bytes + self.attr_bytes
		self.cell_size_bytes = self.letter_bytes + self.offset_bytes


	def serialize_tree(self, dic_tree):
		# magic
		self.data = bytearray( DicSerializer.Magic )
		# version
		self.data.extend( self.version.to_bytes( 2, byteorder='little'))
		# tree
		self.serialize_node( dic_tree.root )
		return self.data


	def deserialize_tree(self, data):
		# magic
		magic = data[0:len(DicSerializer.Magic)]
		if magic != DicSerializer.Magic:
			raise ValueError( "Failed to check magic: " + str( magic ) )
		# version
		v_offset = len(DicSerializer.Magic)
		v = int.from_bytes( data[v_offset: v_offset + 2], byteorder='little' )
		self.init_version( v )
		# tree
		tree = DicTree()
		self.data = data
		self.deserialize_node(tree.root, DicSerializer.HeaderSize)
		return tree


	def serialize_node(self, node):
		# сохраняем текущее смещение - начало записи об этом узле
		offset = len(self.data)
		
		# количество детей (child_count_bytes байтов)
		self.write_int( offset, len(node.keys), self.child_count_bytes )

		# данные в этом узле (attr_bytes байтов)
		node_data = DicNode.NotLeaf if (node.data is None) else node.data
		self.write_int( offset + self.child_count_bytes, node_data, self.attr_bytes )

		# таблица детей
		# по 4 байта на ключ и смещение (количество смещений равно количеству ключей)
		# временно нули. Потом впишем в эту таблицу
		self.data.extend( len( node.keys ) * self.cell_size_bytes * b'\x00' )

		table_offset = offset + self.before_table_bytes
		for i in range( len(node.keys) ):
			child_offset = self.serialize_node( node.children[i] )
			cell_offset = table_offset + self.cell_size_bytes*i
			self.write_key( cell_offset, node.keys[i])
			self.write_int( cell_offset + self.letter_bytes, child_offset, self.offset_bytes )

		return offset


	def deserialize_node(self, node, offset = 0):
		children_count = self.read_int( offset, self.child_count_bytes )
		node_data = self.read_int( offset + self.child_count_bytes, self.attr_bytes )
		node.data = node_data if node_data != DicNode.NotLeaf else None

		table_offset = offset + self.before_table_bytes
		for i in range( children_count ):
			cell_offset = table_offset + self.cell_size_bytes*i
			node.keys.append( self.read_key( cell_offset ) )
			
			child_offset = self.read_int( cell_offset + self.letter_bytes, self.offset_bytes )
			child = DicNode()
			self.deserialize_node( child, child_offset )
			node.children.append( child )


	def write_int(self, where, what, size):
		self.data[where : where + size] = what.to_bytes( size, byteorder='little', signed=True )

	def read_int(self, where, size):
		return int.from_bytes( self.data[where : where + size], byteorder='little', signed=True )

	def write_key( self, offset, letter ):
		self.write_int(offset, ord(letter), self.letter_bytes)

	def read_key( self, offset ):
		return chr( self.read_int( offset, self.letter_bytes ) )


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

	def serialize(self):
		s = DicSerializer()
		return s.serialize_tree( self )


	def deserialize(self, data):
		s = DicSerializer()
		tree = s.deserialize_tree( data )
		self.root = tree.root

####################################################################################################

class DicDawg:

	def __init__(self):
		self.root = DicNode()

	def check_word(self, word):
		curr_node = self.root

		for letter in word:
			curr_node = curr_node.next(letter)
			if curr_node is None:
				return False

		return curr_node.is_leaf()

####################################################################################################

class DicDawgBuilder:

	def __init__(self):
		self.tree = DicTree()
		self.nodes_hash_table = dict()


	def add_word(self, word):
		self.tree.add_word( word )


	def minimize_node(self, node):
		nodes_hash_table = self.nodes_hash_table

		for i, child in enumerate( node.children ):
			node.children[i] = child.minimize( nodes_hash_table )

		h = hash( node )
		if h not in nodes_hash_table:
			nodes_hash_table[h] = node
		else:
			for n in nodes_hash_table[h]:
				if node == n:
					return n
			nodes_hash_table[h].append( node )
		return node


	def build(self):
		self.minimize( self.tree.root )


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

class TestDictionarySerialization(unittest.TestCase):

	def test_empty(self):
		dic = DicTree()
		data = dic.serialize()
		# print( data )
		self.assertEqual( len(data), DicSerializer.HeaderSize + 4 + 4 )
		self.assertEqual( data, b'PRFXTR\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff' )


	def test_one_letter(self):
		dic = DicTree()
		dic.add_word("a")
		data = dic.serialize()
		# print( data )
		self.assertEqual( len( data ), DicSerializer.HeaderSize + (4 + 4 + 1*(4 + 4)) + (4 + 4) )
		self.assertEqual( data,
			b'PRFXTR\x00\x00\x01\x00\x00\x00\xff\xff\xff\xff\x61\x00\x00\x00\x18\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' )
		# 01000000 ffffffff 61000000 08000000 00000000 00000000
		# ^^^^^^^^ - количество детей root
		#           ^^^^^^^^ - атрибуты root (NotLeaf)
		#                   ^^^^^^^^ - ключ ребенка
		#                            ^^^^^^^^ - смещение ребенка
		#                                     ^^^^^^^^ - у ребенка нет детей
		#                                              ^^^^^^^^ - аттрибуты ребенка (EmptyLeaf)


	def test_one_word(self):
		dic = DicTree()
		dic.add_word( "hello" )
		data = dic.serialize()
		# 5 букв. Каждая по:
		# 2 байта - количество детей
		# 2 байта - данные в листе
		# 2 байта - закодирована буква ребенка
		# 2 байта - смещение ребенка
		# корень совпадает с буквой
		# листовой узел не имеет детей. (ровно 4 байта)
		self.assertEqual( len(data), DicSerializer.HeaderSize + 5*(4+4+4+4) + (4+4) )

	def test_one_word_reload(self):
		dic = DicTree()
		dic.add_word( "anyone" )
		data = dic.serialize()
		dic2 = DicTree()
		dic2.deserialize( data )
		self.assertTrue( dic2.check_word( "anyone" ) )
		self.assertFalse( dic2.check_word( "any" ) )

if __name__ == "__main__":
	unittest.main()
