import sys
import argparse
import dictionary

DescriptionString = "Prefix Tree dictionary compiler."

def parse_args():
	parser = argparse.ArgumentParser( prog = "compile_dictionary.py", description = DescriptionString )
	parser.add_argument( "-i", "--input", type=argparse.FileType( "r", encoding='UTF-8' ),
		help = "Path to UTF-8 text file. Words delimeted by any space symbol. If not set, stdin will be used",
		default = sys.stdin )
	parser.add_argument( "-o", "--output", type=argparse.FileType( "wb" ),
		help = "Path to output file. If not set, stdout will be used",
		default = sys.stdout )

	return parser.parse_args()

def main():
	args = parse_args()

	dic = dictionary.DicTree()

	for line in args.input:
		for word in line.split():
			dic.add_word( word )

	binary = dic.serialize()
	args.output.write( binary )



if __name__ == "__main__":
	main()