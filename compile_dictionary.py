#! python3

import sys
import argparse
import dictionary
import time

DescriptionString = "Prefix Tree dictionary compiler."

def parse_args():
	parser = argparse.ArgumentParser( prog = "compile_dictionary.py", description = DescriptionString )
	parser.add_argument( "-i", "--input",
		type=argparse.FileType( "r", encoding='utf16' ),
		help = "Path to UTF-8 text file. Words delimeted by any space symbol. If not set, stdin will be used",
		default = sys.stdin )
	parser.add_argument( "-o", "--output",
		type=argparse.FileType( "wb" ),
		help = "Path to output file. If not set, stdout will be used",
		default = sys.stdout )
	parser.add_argument( "--dawg",
		action='store_const', const=True, default=False,
		help = "Use DAWG(directed acyclic word graph) minimization" )

	return parser.parse_args()

def main():
	args = parse_args()

	collector = dictionary.DicDawgBuilder() if args.dawg else dictionary.DicTree()

	for line in args.input:
		for word in line.split():
			collector.add_word( word )

	binary = bytes()

	start = time.time()

	if args.dawg:
		binary = collector.build().serialize()
	else:
		binary = collector.serialize()

	end = time.time()

	print( "Elapsed time: ", end - start, "s" )

	args.output.write( binary )


if __name__ == "__main__":
	main()
