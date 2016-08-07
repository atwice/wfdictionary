#! python3

import bisect

def add_to_hash( hash, to_add ):
	return (( hash * 0x01000193 ) ^ to_add ) & 0xffffffff


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


	def replace(self, letter, child):
		i = bisect.bisect_left(self.keys, letter)
		if i >= len(self.keys) or self.keys[i] != letter:
			raise Exception( "Error: child not found: " + letter + " in " + str( self.keys ) )
		self.children[i] = child
		self.hash = self._do_calc_hash()


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
		if self.hash is None:
			self.hash = self._do_calc_hash()
		return self.hash

	def _do_calc_hash(self):
		h = 0x01000193
		l = len( self.keys )
		h = add_to_hash( h, l )
		h = add_to_hash( h, self.data if self.data is not None else DicNode.NotLeaf )
		
		while l > 0:
			l -= 1
			h = add_to_hash( h, ord( self.keys[l] ) )
			h = add_to_hash( h, hash( self.children[l] ) )
		return h


####################################################################################################

class DicSerializer:

	MagicTree = b'WFTREE'
	MagicDawg = b'WFDAWG'
	HeaderSize = len( MagicTree ) + 2

	def __init__(self, v = 1):
		self.init_version( v )
		self.data = bytearray()


	def init_version(self, v):
		self.version = v
		if v == 0:
			self.child_count_bytes = 4
			self.attr_bytes = 4
			self.letter_bytes = 4
			self.offset_bytes = 4
		elif v == 1:
			self.child_count_bytes = 1
			self.attr_bytes = 1
			self.letter_bytes = 2
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
		try:
			self.write_int(offset, ord(letter), self.letter_bytes)
		except OverflowError as e:
			print( "Can't save letter", ord( letter ) )
			raise e

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

def common_prefix_length( s1, s2 ):
	i = 0
	l = min( len(s1), len(s2) )
	while (i < l) and (s1[i] == s2[i]):
		i += 1
	return i

debug = False

class DicDawgBuilder:

	def __init__(self):
		self.root = DicNode()
		self.previous_word = ""
		
		# список последних непроверенных узлов. Всегда в порядке возрастания глубины узла
		self.unchecked = []
		# узлы, которые точно нужны в DAWG. 
		self.minimized_nodes = {}

	def add_word(self, word, attr = DicNode.EmptyLeaf ):
		if word < self.previous_word:
			raise Exception( "Error: Words must be inserted in alphabetical order: ", word, self.previous_word )
		self._do_add_word( word, attr )


	def _do_add_word(self, word, attr):
		common_prefix = common_prefix_length( word, self.previous_word )
		self._minimize( common_prefix )

		# [2] - это индекс в кортеже (parent, letter, node)
		node = self.unchecked[-1][2] if len(self.unchecked) > 0 else self.root

		# собственно, добавляем новые узлы
		for letter in word[common_prefix:]:
			next_node = node.add( letter )
			self.unchecked.append( (node, letter, next_node) )
			node = next_node

		node.set_leaf( attr )
		self.previous_word = word


	def _minimize(self, depth):
		for i in range( len(self.unchecked) - 1, depth - 1, -1 ):
			(parent, letter, child) = self.unchecked[i]
			
			if child in self.minimized_nodes:
				parent.replace( letter, self.minimized_nodes[child] )
			else:
				self.minimized_nodes[child] = child
			self.unchecked.pop()


	def build(self):
		self._minimize( 0 )
		return DicDawg( self.root )


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
		dic.add_word("any")
		dic.add_word("anyone")
		dic.add_word("anywhere")
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
		s = DicSerializer(v=0)
		data = s.serialize_tree(dic)
		# print( data )
		self.assertEqual( len(data), DicSerializer.HeaderSize + 4 + 4 )
		self.assertEqual( data, b'WFTREE\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff' )


	def test_one_letter(self):
		dic = DicTree()
		dic.add_word("a")
		s = DicSerializer(v=0)
		data = s.serialize_tree(dic)
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
		s = DicSerializer(v=0)
		data = s.serialize_tree(dic)
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
		builder.add_word( "any" )
		builder.add_word( "anyone" )
		builder.add_word( "anywhere" )
		builder.add_word( "someone" )
		builder.add_word( "somewhere" )
		self.builder = builder

	def test_empty(self):
		dic = DicDawg()
		s = DicSerializer(v=0)
		data = s.serialize_dawg(dic)
		# print( data )
		self.assertEqual( len(data), DicSerializer.HeaderSize + 4 + 4 )
		self.assertEqual( data, b'WFDAWG\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff' )

	def test_one_final(self):
		global debug
		debug = True
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
		debug = False

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


class TestCommonPrefix(unittest.TestCase):
	def test_all(self):
		self.assertEqual( common_prefix_length("","abc"), 0)
		self.assertEqual( common_prefix_length("a","abc"), 1)
		self.assertEqual( common_prefix_length("bac","abc"), 0)
		self.assertEqual( common_prefix_length("abc","abc"), 3)
		self.assertEqual( common_prefix_length("abcdef","abc"), 3)


if __name__ == "__main__":
	unittest.main()
