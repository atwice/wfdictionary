#! python3

import pickle

START = "S"

class FSM:

	def __init__(self):
		self.states = { START: {} }
		self.final = set()
		self.terminal_alphabet = set()

	def has_state(self, name):
		return name in self.states

	def add_state(self, state_name):
		if state_name in self.states:
			raise Exception( "Error: State already in machine" )
		self.states[state_name] = {}

	def check_has_state(self, state_name):
		if state_name not in self.states:
			raise Exception( "Error: Unknown state: " + state_name )

	def set_final(self, state_name):
		self.check_has_state( state_name )
		self.final.add( state_name )

#------------------------------------------------------------------------------

# Детерминированный КА.
# Каждое состояние - { term_elem : state_name }
# + set конечных состояний
# + множество терминалов (алфавит)
class DFA(FSM):

	def add_trans(self, from_state, terminal, to_state):
		self.terminal_alphabet.add( terminal )
		self.check_has_state( from_state )
		if not self.has_state( to_state ):
			self.add_state( to_state )
		if terminal in self.states[from_state] and self.states[from_state][terminal] != to_state:
			print( from_state, terminal, to_state )
			print( self.states[from_state][terminal] )
			raise Exception( "Error. DFA already has transition: " + from_state  + " , " + str( terminal ) )
		self.states[from_state][terminal] = to_state


	def check(self, word):
		current = START
		for w in word:
			if w not in self.terminal_alphabet:
				raise Exception( "Error. Symbol not in terminal alphabet: " + w )
			state = self.states[current]
			if w not in state:
				return False
			current = state[w]
			# детерминированность
			assert isinstance( current, str )
		return current in self.final

	def serialize(self, out_stream):
		pickler.dump( self, out_stream )

	def deserialize( in_stream ):
		return unpickler.load( in_stream )

	# выводит себя в текстовый поток
	def write_as_text(self, output):
		for state_name in self.states.keys():
			state = self.states[state_name]
			for terminal in state.keys():
				target = state[terminal]
				output.write( state_name + " : " + str(terminal) + " -> " + target + "\n" )

	def from_start(self):
		return DFA.State( self, START )

	# вложенный класс DFA.State для доступа к отдельным состояниям
	class State:

		def __init__(self, dfa, state_name):
			self.dfa = dfa
			self.state_name = state_name

		def next(self, term):
			state = self.dfa.states[self.state_name]
			if term not in state:
				return None
			next_state = state[term]
			# детерминированность
			assert isinstance( next_state, str )
			return DFA.State( self.dfa, next_state )

		def is_final(self):
			return self.state_name in self.dfa.final


#------------------------------------------------------------------------------


# Недетерминированный КА.
# Каждое состояние - { term_elem : [state_names] }
# + set конечных состояний
# + множество терминалов (алфавит)
class NFA(FSM):

	def add_trans(self, from_state, terminal, to_state):
		self.terminal_alphabet.add( terminal )
		self.check_has_state( from_state )
		if not self.has_state( to_state ):
			self.add_state( to_state )
		if terminal not in self.states[from_state]:
			self.states[from_state][terminal] = []
		if to_state not in self.states[from_state][terminal]:
			self.states[from_state][terminal].append( to_state )


	def check(self, word):
		current = START
		for w in word:
			if w not in self.terminal_alphabet:
				raise Exception( "Error. Symbol not in terminal alphabet: " + w )
			state = self.states[current]
			# print( w, state )
			if w not in state:
				return False
			current = state[w]
			if len( current ) > 1:
				raise Exception( "Error. Checking by non-determinant NFA. Please, convert to_DFA.")
			current = current[0]
		return current in self.final


	# пока не поддерживаем epsilon-переходы
	def to_DFA(self):

		# вспомогательная функция для кодирования имен сложных состояний
		def mangle( names ):
			names = sorted( names )
			return "@" + "_".join( names )

		dfa = DFA()
		dfa.terminal_alphabet= self.terminal_alphabet
		
		processed = set()
		# список к обработке [ (имя в новом автомате, [список имен состояний в старом автомате]) ]
		states_to_process = [(START, [START])]
		
		while len( states_to_process ) > 0:
			new_state, old_states = states_to_process.pop(0)
			processed.add( new_state )
			
			transfers = {} # { terminal : [имена состояний]}
			is_final = False
			# перебираем старые состояния, которые объединяем в new_state
			for old_state_name in old_states:
				
				# проверка, что объединение будет финализирующим состоянием
				is_final |= (old_state_name in self.final)
				
				# объект состояния
				old_state = self.states[old_state_name]
				# перебираем все переходы
				for term in old_state.keys():
					if term not in transfers:
						transfers[term] = []
					# недетерминизм. по term имеется несколько альтернатив
					for old_target_name in old_state[term]:
						if old_target_name not in transfers[term]:
							transfers[term].append( old_target_name )
			
			if is_final:
				dfa.set_final( new_state )

			for term in transfers.keys():
				union_state = mangle( transfers[term] )
				dfa.add_trans( new_state, term, union_state )
				if union_state not in processed:
					states_to_process.append( (union_state, transfers[term]) )

		return dfa

	# выводит себя в текстовый поток
	def write_as_text(self, output):
		for state_name in self.states.keys():
			state = self.states[state_name]
			for terminal in state.keys():
				transfers = state[terminal]
				for tr in transfers:
					output.write( state_name + " : " + str(terminal) + " -> " + tr + "\n" )

#------------------------------------------------------------------------------

import unittest

class TestNFA(unittest.TestCase):
	def setUp(self):
		fsm = NFA()
		fsm.add_trans( START, "a", START )
		fsm.add_trans( START, "b", START )
		fsm.add_trans( START, "a", "Q1" )
		fsm.add_trans( "Q1", "b", "Q2" )
		fsm.set_final( "Q2" )

		self.dfa = fsm.to_DFA()

	def test_any_ab(self):
		dfa = self.dfa

		self.assertFalse( dfa.check( "" ) )
		self.assertFalse( dfa.check( "a" ) )
		self.assertFalse( dfa.check( "b" ) )
		self.assertTrue( dfa.check( "ab" ) )
		self.assertTrue( dfa.check( "aab" ) )
		self.assertTrue( dfa.check( "bab" ) )
		self.assertFalse( dfa.check( "aba" ) )
		self.assertFalse( dfa.check( "bba" ) )

	# проверяем интерфейс NFA.State
	def test_per_state_interface(self):
		dfa = self.dfa

		state = dfa.from_start()
		self.assertIsNotNone( state )
		self.assertFalse( state.is_final() )
		
		state = state.next( "a" )
		self.assertIsNotNone( state )
		self.assertFalse( state.is_final() )

		state = state.next( "a" )
		self.assertIsNotNone( state )
		self.assertFalse( state.is_final() )

		state = state.next( "b" )
		self.assertIsNotNone( state )
		self.assertTrue( state.is_final() )


	# автомат принимает число, первая цифра которого повторяется в этом числе
	def test_any_digits_last_was_before(self):
		fsm = NFA()
		fsm.add_trans( START, "1", "Q1" )
		fsm.add_trans( START, "2", "Q2" )
		fsm.add_trans( START, "3", "Q3" )
		fsm.add_trans( "Q1", "1", "F" )
		fsm.add_trans( "Q2", "2", "F" )
		fsm.add_trans( "Q3", "3", "F" )
		fsm.add_trans( "Q1", "2", "Q1" )
		fsm.add_trans( "Q1", "3", "Q1" )
		fsm.add_trans( "Q2", "1", "Q2" )
		fsm.add_trans( "Q2", "3", "Q2" )
		fsm.add_trans( "Q3", "2", "Q3" )
		fsm.add_trans( "Q3", "1", "Q3" )
		fsm.add_trans( "F", "1", "F" )
		fsm.add_trans( "F", "2", "F" )
		fsm.add_trans( "F", "3", "F" )
		fsm.set_final( "F" )

		dfa = fsm.to_DFA()
		
		self.assertFalse( dfa.check( "123" ) )
		self.assertFalse( dfa.check( "13" ) )
		self.assertFalse( dfa.check( "2111111111" ) )
		self.assertTrue( dfa.check( "11" ) )
		self.assertTrue( dfa.check( "213213" ) )
		self.assertTrue( dfa.check( "31111113" ) )
		self.assertFalse( dfa.check( "213131313" ) )
		self.assertFalse( dfa.check( "322221111" ) )

	# автомат принимает число, первая цифра которого повторяется в этом числе
	def test_number_terminal(self):
		fsm = NFA()
		fsm.add_trans( START, 1, "Q1" )
		fsm.add_trans( START, 2, "Q2" )
		fsm.add_trans( "Q1", 1, "F" )
		fsm.add_trans( "Q2", 2, "F" )
		fsm.add_trans( "Q1", 2, "Q1" )
		fsm.add_trans( "Q2", 1, "Q2" )
		fsm.add_trans( "F", 1, "F" )
		fsm.add_trans( "F", 2, "F" )
		fsm.set_final( "F" )

		dfa = fsm.to_DFA()
		
		self.assertFalse( dfa.check( [1,2] ) )
		self.assertFalse( dfa.check( [2,1] ) )
		self.assertFalse( dfa.check( [2,1,1,1] ) )
		self.assertTrue( dfa.check( [1,1] ) )
		self.assertTrue( dfa.check( [2,1,2,1] ) )

	def test_encoded(self):
		enc = self.dfa.to_EncodedDFA()

		a = ord("a")
		b = ord("b")
		self.assertFalse( enc.check( [] ) )
		self.assertFalse( enc.check( [a] ) )
		self.assertFalse( enc.check( [b] ) )
		self.assertTrue( enc.check( [a,b] ) )
		self.assertTrue( enc.check( [a, a, b] ) )
		self.assertTrue( enc.check( [b, a, b] ) )
		self.assertFalse( enc.check( [a, b, a] ) )
		self.assertFalse( enc.check( [b, b, a] ) )

if __name__ == "__main__":
	unittest.main()