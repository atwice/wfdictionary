#! python3

import sys
import argparse
import dictionary
import time
import io

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

	input = args.input
	input.seek( 0, io.SEEK_END )
	total_bytes = input.tell()
	input.seek( 0, io.SEEK_SET )

	start = time.time()

	i = 0
	current_bytes = 0

	for line in input:
		for word in sorted(line[:-1].split()):
			collector.add_word( word )
			i += 1
			current_bytes += len( line ) * 2
		if i > 10000:
			print( "{:.2%}".format( current_bytes / total_bytes ), end='\r' )
			i = 0

	binary = bytes()

	build_end = time.time()

	if args.dawg:
		binary = collector.build().serialize()
	else:
		binary = collector.serialize()

	serialize_end = time.time()

	args.output.write( binary )

	end = time.time()

	print( "Building DAWG time: ", build_end - start, "s" )
	print( "Serialization time: ", serialize_end - build_end, "s" )
	print( "Total time: ", end - start, "s" )


if __name__ == "__main__":
	main()
