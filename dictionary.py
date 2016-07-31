import bisect

class DicNode:

	NotLeaf = -1
	EmptyLeaf = 0

	def encode_int( integer ):
		return integer.to_bytes( 4, byteorder='little', signed=True )

	def decode_int( buffer, offset ):
		return int.from_bytes( buffer[offset : offset + 4], byteorder='little', signed=True )

	def encode_key( letter ):
		return DicNode.encode_int( ord( letter ) )

	def decode_key( buffer, offset ):
		return chr( DicNode.decode_int( buffer, offset ) )

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

	def serialize(self, buffer):
		# сохраняем текущее смещение - начало записи об этом узле
		offset = len(buffer)
		
		# количество детей
		buffer.extend( DicNode.encode_int( len(self.keys) ) )

		# данные в этом узле (4 байта)
		node_data = DicNode.NotLeaf if (self.data is None) else self.data
		buffer.extend( DicNode.encode_int( node_data ) )

		# таблица детей
		# по 4 байта на ключ и смещение (количество смещений равно количеству ключей)
		# временно нули. Потом перепишем
		buffer.extend( len( self.keys ) * 8 * b'\x00' )

		for i in range( len(self.keys) ):
			child_offset = self.children[i].serialize(buffer)
			
			key_offset = offset + 8 + 8*i
			buffer[key_offset : key_offset + 4] = DicNode.encode_key( self.keys[i] )
			child_table_offset = key_offset + 4
			buffer[child_table_offset : child_table_offset + 4] = DicNode.encode_int( child_offset )

		return offset


	def deserialize(self, buffer, offset = 0):
		children_count = DicNode.decode_int( buffer, offset )
		node_data = DicNode.decode_int( buffer, offset + 4 )
		self.data = node_data if node_data != DicNode.NotLeaf else None

		for i in range( children_count ):
			key_offset = offset + 8 + 8*i
			self.keys.append( DicNode.decode_key( buffer, key_offset ) )
			
			child_offset = DicNode.decode_int( buffer, key_offset + 4 )
			child = DicNode()
			child.deserialize( buffer, child_offset )
			self.children.append( child )


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
		data = bytearray()
		assert len(data) == 0
		self.root.serialize(data)
		return bytes(data)

	def deserialize(self, data):
		self.root = DicNode()
		self.root.deserialize(data)

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
		# b'\x00\x00\xff\xff'
		self.assertEqual( len(data), 4 + 4 )
		self.assertEqual( data, b'\x00\x00\x00\x00\xff\xff\xff\xff' )

	def test_one_letter(self):
		dic = DicTree()
		dic.add_word("a")
		data = dic.serialize()
		# print( data )
		self.assertEqual( len( data ), (4 + 4 + 1*(4 + 4)) + (4 + 4) )
		self.assertEqual( data,
			b'\x01\x00\x00\x00\xff\xff\xff\xff\x61\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' )
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
		self.assertEqual( len(data), 5*(4+4+4+4) + (4+4) )

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
