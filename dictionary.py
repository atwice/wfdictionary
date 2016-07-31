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
		return self.data == other.data and \
			self.keys == other.keys and \
			self.children == other.children


	def __hash__(self):
		if self.hash is not None:
			return self.hash

		h = 0
		l = len( self.keys )
		h = add_to_hash( h, l )
		h = add_to_hash( h, self.data if self.data is not None else DicNode.NotLeaf )
		
		while l > 0:
			l -= 1
			h = add_to_hash( h, ord( self.keys[l] ) )
			h = add_to_hash( h, hash( self.children[l] ) )

		self.hash = h
		return self.hash


####################################################################################################

class DicSerializer:

	MagicTree = b'WFTREE'
	MagicDawg = b'WFDAWG'
	HeaderSize = len( MagicTree ) + 2

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


	def serialize_dawg(self, dic_dawg):
		# magic
		self.data = bytearray( DicSerializer.MagicDawg )
		# version
		self.data.extend( self.version.to_bytes( 2, byteorder='little'))
		# tree
		self.serialize_node( dic_dawg.root )
		return self.data


	def serialize_tree(self, dic_tree):
		# magic
		self.data = bytearray( DicSerializer.MagicTree )
		# version
		self.data.extend( self.version.to_bytes( 2, byteorder='little'))
		# tree
		self.serialize_node( dic_tree.root )
		return self.data


	def deserialize(self, data):
		self.data = data
		self.dawg_deserialization_cache = dict()
		magic = data[0:len(DicSerializer.MagicTree)]
		if magic == DicSerializer.MagicTree:
			root = self.deserialize_node(DicSerializer.HeaderSize, False)
			return DicTree( root )
		elif magic == DicSerializer.MagicDawg:
			root = self.deserialize_node(DicSerializer.HeaderSize, True)
			return DicDawg( root )
		else:
			raise ValueError( "Unknown magic: " + str( magic ) )


	def serialize_node(self, node):
		# поддержка DAWG
		if hasattr( node, "_serialization_offset" ):
			return node._serialization_offset

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

		node._serialization_offset = offset
		return offset


	def deserialize_node(self, offset, is_dawg):
		if is_dawg:
			# имеет смысл поискать в кэше
			node = self.dawg_deserialization_cache.get( offset, None )
			if node is not None:
				return node
		
		node = DicNode()
		children_count = self.read_int( offset, self.child_count_bytes )
		node_data = self.read_int( offset + self.child_count_bytes, self.attr_bytes )
		node.data = node_data if node_data != DicNode.NotLeaf else None

		table_offset = offset + self.before_table_bytes
		for i in range( children_count ):
			cell_offset = table_offset + self.cell_size_bytes*i
			node.keys.append( self.read_key( cell_offset ) )
			
			child_offset = self.read_int( cell_offset + self.letter_bytes, self.offset_bytes )
			child = self.deserialize_node( child_offset, is_dawg )
			node.children.append( child )
		
		if is_dawg:
			self.dawg_deserialization_cache[offset] = node

		return node


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

	def __init__(self, root = None):
		self.root = root if (root is not None) else DicNode()


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
		tree = s.deserialize( data )
		self.root = tree.root

####################################################################################################

class DicDawg:

	def __init__(self, root = None):
		self.root = root if (root is not None) else DicNode()

	def check_word(self, word):
		curr_node = self.root

		for letter in word:
			curr_node = curr_node.next(letter)
			if curr_node is None:
				return False

		return curr_node.is_leaf()

	def serialize(self):
		s = DicSerializer()
		return s.serialize_dawg( self )

	def deserialize(self, data):
		s = DicSerializer()
		dawg = s.deserialize(data)
		self.root = dawg.root


####################################################################################################

class DicDawgBuilder:

	def __init__(self):
		self.tree = DicTree()
		self.nodes_hash_table = dict()


	def add_word(self, word):
		self.tree.add_word( word )


	def minimize_node(self, node):
		hash_table = self.nodes_hash_table

		for i, child in enumerate( node.children ):
			node.children[i] = self.minimize_node( child )

		h = hash( node )
		if h not in hash_table:
			hash_table[h] = [node]
		else:
			for n in hash_table[h]:
				if node == n:
					return n
			hash_table[h].append( node )
		return node


	def build(self):
		self.minimize_node( self.tree.root )
		return DicDawg( self.tree.root )


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


###


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


###


class TestDictionarySerialization(unittest.TestCase):

	def test_empty(self):
		dic = DicTree()
		data = dic.serialize()
		# print( data )
		self.assertEqual( len(data), DicSerializer.HeaderSize + 4 + 4 )
		self.assertEqual( data, b'WFTREE\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff' )


	def test_one_letter(self):
		dic = DicTree()
		dic.add_word("a")
		data = dic.serialize()
		# print( data )
		self.assertEqual( len( data ), DicSerializer.HeaderSize + (4 + 4 + 1*(4 + 4)) + (4 + 4) )
		self.assertEqual( data,
			b'WFTREE\x00\x00\x01\x00\x00\x00\xff\xff\xff\xff\x61\x00\x00\x00\x18\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' )
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


###


class TestDawg(unittest.TestCase):
	def setUp(self):
		builder = DicDawgBuilder()
		builder.add_word( "anyone" )
		builder.add_word( "anywhere" )
		builder.add_word( "any" )
		builder.add_word( "someone" )
		builder.add_word( "somewhere" )
		self.builder = builder

	def test_empty(self):
		dic = DicDawg()
		data = dic.serialize()
		# print( data )
		self.assertEqual( len(data), DicSerializer.HeaderSize + 4 + 4 )
		self.assertEqual( data, b'WFDAWG\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff' )

	def test_one_final(self):
		tree = DicTree()
		tree.add_word( "a" )
		tree.add_word( "b" )
		tree_data = tree.serialize()
		
		builder = DicDawgBuilder()
		builder.add_word( "a" )
		builder.add_word( "b" )
		dawg = builder.build()
		dawg_data = dawg.serialize()

		self.assertLess( len( dawg_data ), len( tree_data ) )

	def test_words(self):
		dawg = self.builder.build()
		
		self.assertTrue( dawg.check_word("anyone") )
		self.assertTrue( dawg.check_word("anywhere") )
		self.assertTrue( dawg.check_word("any") )
		self.assertTrue( dawg.check_word("someone") )
		self.assertTrue( dawg.check_word("somewhere") )
		self.assertFalse( dawg.check_word("some") )
		self.assertFalse( dawg.check_word("a") )
		self.assertFalse( dawg.check_word("an") )
		self.assertFalse( dawg.check_word("anyo") )
		self.assertFalse( dawg.check_word("anyon") )


	def test_reload(self):
		dawg = self.builder.build()
		dawg_data = dawg.serialize()
		dawg2 = DicDawg()
		dawg2.deserialize( dawg_data )

		self.assertTrue( dawg2.check_word("anyone") )
		self.assertTrue( dawg2.check_word("anywhere") )
		self.assertTrue( dawg2.check_word("any") )
		self.assertTrue( dawg2.check_word("someone") )
		self.assertTrue( dawg2.check_word("somewhere") )
		self.assertFalse( dawg2.check_word("some") )
		self.assertFalse( dawg2.check_word("a") )
		self.assertFalse( dawg2.check_word("an") )
		self.assertFalse( dawg2.check_word("anyo") )
		self.assertFalse( dawg2.check_word("anyon") )


if __name__ == "__main__":
	unittest.main()
