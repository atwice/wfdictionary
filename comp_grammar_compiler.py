#! python3

import sys
import fsm
import dictionary as dic

# единственный аргумент
Language = sys.argv[1]

# файл с комп. грамматикой вида:
# 1 + 0 -> 0
# 0 + 21 -> 22
CompGrammarFile = open( Language + "_CompositeRules_Grammar.txt", encoding="utf-16" )

# файл с отношением между грамматическими фильтрами
# задаёт частичный порядок над грамматическими фильтрами
# 0 < 1
# означает, что фильтр 1 требует все те же граммемы, что фильтр 0
GrammarFilterRelation = open( Language + "_GrammarFilterRel.txt", encoding="utf-16" )

# Словарь
# слово <тэг из номеров композитных фильтров>
Dictionary = open( Language + "_Dictionary.txt", encoding="utf-16" )

FINAL = "FINAL"

def read_grammar():
	grammar = []
	CompGrammarFile.seek( 0 )
	for line in CompGrammarFile:
		parts = line[:-1].split()
		if len( parts ) < 5:
			continue
		left, _plus, right, _arrow, res = parts
		grammar.append( (res, left, right) )
	return grammar

def output_grammar( file_name, grammar ):
	out = open( file_name, "w", encoding="utf-16" )
	for (res, left, right) in grammar:
		out.write( res + " -> " + left + " " + right + "\n" )


def read_filter_relation():
	result = {}
	GrammarFilterRelation.seek( 0 )
	for line in GrammarFilterRelation:
		parts = line[:-1].split()
		if len( parts ) != 3:
			# формат 0 < 22
			continue
		left, _less, right = parts
		if left not in result:
			result[left] = []
		result[left].append( right )

	return result



def inflate_grammar( grammar, gr_filter_rel ):
	new_rules = []
	
	def append_new_rule( nr ): # nr = new_rule
		if nr not in new_rules and nr not in grammar:
			new_rules.append( nr )

	for (res, left, right) in grammar:
		if res == left and left in gr_filter_rel:
			variants = gr_filter_rel[left]
			for v in variants:
				append_new_rule( (v, v, right) )

		elif res == right and right in gr_filter_rel:
			variants = gr_filter_rel[right]
			for v in variants:
				append_new_rule( (v, left, v) )
	return grammar + new_rules


def nonterm( number ):
	return "G" + number


def term( number ):
	return "t" + number

def build_trivial_transfers( grammar, nfa ):
	for (res, left, right) in grammar:
		add_terminal_transfer( res, nfa )
		add_terminal_transfer( left, nfa )
		add_terminal_transfer( right, nfa )

# Результирующее правило
# G1 -> t1
def add_terminal_transfer( number, nfa ):
	non_term_name = nonterm( number )
	if nfa.has_state( non_term_name ):
		return
	nfa.add_state( non_term_name )
	nfa.add_trans( non_term_name, term(number), FINAL )


def add_dependency( dependencies, dependent, independent ):
	if independent not in dependencies:
		dependencies[independent] = []
	# независимый -> зависимый
	dependencies[independent].append( dependent )

# правое ядро: R -> L R
def add_right_core_rules( left, right, dependencies, nfa ):
	left_terminal = term( left )
	right_non_term = nonterm( right )
	# 1. Любой разбор может быть последним. (S -> R) => S -> l R
	nfa.add_trans( fsm.START, left_terminal, right_non_term )
	# 2. Правое ядро (R -> L R) => R -> l R
	nfa.add_trans( right_non_term, left_terminal, right_non_term )

# левое ядро: L -> L R
def add_left_core_rules( left, right, dependencies, nfa ):
	left_non_term = nonterm( left )
	left_term = nonterm( left )
	right_term = term( right )
	# 1. Любой разбор может быть последним
	state_before_final = right_term + "_FINAL"
	nfa.add_trans( fsm.START, left_term, state_before_final )
	nfa.add_trans( state_before_final, right_term, FINAL )
	# 2. Саморекурсия. l r+
	# L -> l R+
	# R+ -> r R+ | r
	right_recursive = nonterm( right ) + "+"
	nfa.add_trans( left_non_term, left_term, right_recursive )
	nfa.add_trans( right_recursive, right_term, right_recursive )
	nfa.add_trans( right_recursive, right_term, FINAL )


# зависимость правоядерного от правоядерного
# A -> B A
# B -> C B
# A зависит от B
# принимаем слова вида (c+ b)+ a
# отложенное состояние B_A (ведем себя как B, но обещаем вернуться в A)
# 1. A -> c B>A (подстановка терминала)
# 2. B>A -> c B>A (ведем себя как B - правоядерность)
# 3. B>A -> b A (откладывали A - возвращаемся)
def process_depend_right_right( left, right, dependent, nfa ):
	dep_non_term = nonterm( dependent ) # A
	deffered = nonterm( right ) + ">" + dep_non_term # B>A
	left_term = term( left ) # c
	final_term = term( right ) # b
	# 1. A -> c B_A
	nfa.add_trans( dep_non_term, left_term, deffered )
	# 2. B_A -> c B_A
	nfa.add_trans( deffered, left_term, deffered )
	# 3. B_A -> b A
	nfa.add_trans( deffered, final_term, dep_non_term )


# зависимость правоядерного от левоядерного
# A -> B A
# B -> B С
# A зависит от B
# принимаем слова вида (b c+)+ a
# отложенное состояние B^C+_A (ведем себя как B -> B C, но обещаем вернуться в A)
# 1. A -> b B^C+_A
# 2. B^C+_A -> c B^C+_A (ведем себя как B -> B C)
# 3. B^C+_A -> c A (для рекурсии скобок (b c+)+ )
# 4. B^C+_A -> a FINAL (откладывали a)
def process_depend_right_left( left, right, dependent, nfa ):
	dep_term = term( dependent ) # a
	left_term = term( left ) # b
	right_term = term( right ) # c
	dep_non_term = nonterm( dependent ) # A
	special_state = nonterm( left ) + "^" + nonterm( right ) + "+_" + dep_non_term # B^C+_A
	nfa.add_trans( dep_non_term, left_term, special_state )		# 1
	nfa.add_trans( special_state, right_term, special_state )	# 2
	nfa.add_trans( special_state, right_term, dep_non_term )	# 3
	nfa.add_trans( special_state, dep_term, FINAL )				# 4


# зависимость левоядерного от правоядерного
# A -> A B
# B -> С B
# A зависит от B
# принимаем слова вида a(c+b)+
# 1. A -> a C^B0
# 2. C^B0 -> c C^B1
# 3. C^B1 -> c C^B1
# 4. C^B1 -> b C^B2
# 5. C^B1 -> b FINAL
# 6. C^B2 -> c C^B1
def process_depend_left_right( left, right, dependent, nfa ):
	dep_term = term( dependent ) # a
	left_term = term( left ) # c
	right_term = term( right ) # b
	dep_non_term = nonterm( dependent ) # A
	special = nonterm( left ) + "^" + nonterm( right )
	special_0 = special + "0"
	special_1 = special + "1"
	special_2 = special + "2"
	nfa.add_trans( dep_non_term, dep_term, special_0 )	# 1
	nfa.add_trans( special_0, left_term, special_1 )	# 2
	nfa.add_trans( special_1, left_term, special_1 )	# 3
	nfa.add_trans( special_1, right_term, special_2 )	# 4
	nfa.add_trans( special_1, right_term, FINAL )		# 5
	nfa.add_trans( special_2, left_term, special_1 )	# 6

# зависимость левоядерного от левоядерного
# A -> A B
# B -> B C
# A зависит от B
# принимаем слова вида a(bc+)+
# 1. A -> a B^C+
# 2. B^C+ -> b C+_B+
# 3. C+_B+ -> c C+_B+
# 4. C+_B+ -> c B^C+
# 5. C+_B+ -> c FINAL
def process_depend_left_left( left, right, dependent, nfa ):
	dep_term = term( dependent ) # a
	left_term = term( left ) # b
	right_term = term( right ) # c
	dep_non_term = nonterm( dependent ) # A
	special_0 = nonterm( left ) + "^" + nonterm( right ) + "+"	# B^C+
	special_1 = nonterm( right ) + "+_" + nonterm( left ) + "+"	# C+_B+
	nfa.add_trans( dep_non_term, dep_term, special_0 )	# 1 
	nfa.add_trans( special_0, left_term, special_1 )	# 2
	nfa.add_trans( special_1, right_term, special_1 )	# 3
	nfa.add_trans( special_1, right_term, special_0 )	# 4
	nfa.add_trans( special_1, right_term, FINAL )		# 5


def build_fsm( grammar ):
	nfa = fsm.NFA()
	nfa.add_state( FINAL )
	nfa.set_final( FINAL )

	build_trivial_transfers( grammar, nfa )
	
	right_dependencies = {}
	left_dependencies = {}

	# фаза 1. Простые правила. Зависимости будут обработаны на фазе 2.
	for (res, left, right) in grammar:
		if res == left == right:
			pass # чтобы не забыть
		elif res == right:
			# правоядерное правило
			add_right_core_rules( left, right, right_dependencies, nfa )
			add_dependency( right_dependencies, right, left )
		elif res == left:
			# левоядерное правило
			add_left_core_rules( left, right, left_dependencies, nfa )
			add_dependency( left_dependencies, left, right)

	# фаза 2. Обрабатываем зависимости
	for (res, left, right) in grammar:
		if res == left == right:
			pass # TODO: чтобы не забыть
		elif res == right:
			# правоядерное правило
			if res in right_dependencies:
				for dependent in right_dependencies[res]:
					process_depend_right_right( left, right, dependent, nfa )
			if res in left_dependencies:
				for dependent in left_dependencies[res]:
					process_depend_right_left( left, right, dependent, nfa )
		elif res == left:
			# левоядерное правило
			if res in right_dependencies:
				for dependent in right_dependencies[res]:
					process_depend_left_right( left, right, dependent, nfa )
			if res in left_dependencies:
				for dependent in left_dependencies[res]:
					process_depend_left_left( left, right, dependent, nfa )

	return nfa


def compile_dictionary():
	builder = dic.DicDawgBuilder()
	number = 1
	tags_to_number = { "<>": 0 }
	terminals_to_tag = {}

	for line in Dictionary:
		word, tag = line[:-1].split( maxsplit=1 )
		if tag not in tags_to_number:
			tags_to_number[tag] = number
			number += 1

		current_tag_number = tags_to_number[tag]

		builder.add_word( word.strip( " " ), current_tag_number )

		terminals = tag.strip( " <>" ).split()
		for term_number in terminals:
			term_name = term( term_number )
			if term_name not in terminals_to_tag:
				terminals_to_tag[term_name] = []
			if current_tag_number not in terminals_to_tag[term_name]:
				terminals_to_tag[term_name].append( current_tag_number )

	with open( Language + "_dic.dawg", "wb" ) as dawg_out:
		dawg_out.write( builder.build().serialize() )

	return terminals_to_tag


def split_terminals_to_tags( dfsm, term_to_tag ):
	# лезем в исходники FSM
	new_nfa = fsm.NFA()
	processed = set(fsm.START)

	# обход в ширину (BFS)
	to_process = [fsm.START]
	while len( to_process ) > 0:
		current_name = to_process.pop( 0 )
		state = dfsm.states[current_name]
		for term in state.keys():
			if term not in term_to_tag:
				continue
			# в DFA state[term] - единственный элемент
			next_name = state[term]
			for tag in term_to_tag[term]:
				new_nfa.add_trans( current_name, tag, next_name )
			if next_name not in processed:
				processed.add( next_name )
				to_process.append( next_name )
	return new_nfa.to_DFA()


def main():
	grammar = read_grammar()
	gr_filter_rel = read_filter_relation()
	grammar = inflate_grammar( grammar, gr_filter_rel )

	nfa = build_fsm( grammar )
	nfa.write_as_text( open( "nfa.txt", "w" ) )

	dfa = nfa.to_DFA()
	dfa.write_as_text( open( "dfa.txt", "w" ) )

	term_to_tag = compile_dictionary()
	open( "term_to_tag.txt", "w" ).write( str( term_to_tag ) )

	splitted_dfa = split_terminals_to_tags( dfa, term_to_tag )
	splitted_dfa.write_as_text( open( "splitted_dfa.txt", "w" ) )
	with open( Language + "_copm.dfa", "wb" ) as out:
		splitted_dfa.serialize( out )


if __name__ == '__main__':
	main()