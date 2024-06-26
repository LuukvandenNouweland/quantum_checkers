import argparse
from enums import CheckersResult, CheckersRules
from interface import GameInterface
from quantum_checkers import Checkers
import time
from players import * # Imports all possible bots
import math
import cProfile
import pstats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--num_rows', help='The number of rows of the checkboard. INT', default=8)
    parser.add_argument('--num_columns', help='The number of columns of the checkboard. INT', default=8)
    parser.add_argument('--num_vertical_pieces', help='The number of rows that are filled with checkerpieces. INT', default=1)
    parser.add_argument('--sim_q', help='Simulating quantum or actually use quantum mechanics. TRUE if you want to simulate quantum.', default="False")
    parser.add_argument('--GUI', help='If GUI is enabled. True or False', default="False")
    parser.add_argument('--p1', help='Select agent for player 1 to use.', default=human_player())
    parser.add_argument('--p2', help='Select agent for player 2 to use.', default=human_player())
    args = parser.parse_args()
    p1 = human_player()
    p2 = human_player()
    if(args.num_columns % 2 == 1 and args.num_rows % 2 == 0):
        warning_len = len("# WARNING: If the number of columns is uneven and the number of rows is even the board is not symmetrical. #")
        print("#"*warning_len)
        print("# WARNING: If the number of columns is uneven and the number of rows is even the board is not symmetrical. #\n# To assure an equal number of pieces, set the number of vertical pieces to an even value.                 #")
        print("#"*warning_len)
        time.sleep(5)
    file = open("./temp.txt", "a")
    # for rule in [CheckersRules.CLASSICAL, CheckersRules.QUANTUM_V1, CheckersRules.QUANTUM_V2]:
    #     for size in [10, 12, 14]:
    size = 5
    rule = CheckersRules.QUANTUM_V2
    times = []
    results = []
    number_of_moves = []
    file.write("#"*100 + "\n")
    file.write(f"Size: {size}x{size}, Rule: {rule}\n")
    print(f"Size: {size}x{size}, Rule: {rule}")
    for i in range(1000):
        if((i+1)%50 == 0):
            print(i+1)
        start_t = time.time()
        checkers = Checkers(num_vertical=size, num_horizontal=size, num_vertical_pieces=args.num_vertical_pieces, SIMULATE_QUANTUM=args.sim_q, rules=rule)
        game = GameInterface(checkers, white_player=p1, black_player=p2, GUI=args.GUI)
        result, num_moves = (game.play())
        results.append(result)
        number_of_moves.append(num_moves)
        times.append(time.time()-start_t)
        #if((i+1)%100 == 0):
        #    print(f"Draw: {results.count(CheckersResult.DRAW)}, White wins: {results.count(CheckersResult.WHITE_WINS)}, Black wins: {results.count(CheckersResult.BLACK_WINS)}")
        #    print(f"Average number of moves: {sum(number_of_moves)/len(number_of_moves)}")
    print("#"*100)
    print(f"Average time: {sum(times)/len(times)}, minimum time: {min(times)}, max time: {max(times)}")
    print(f"Average number of moves: {sum(number_of_moves)/len(number_of_moves)}")
    print(f"Draw: {results.count(CheckersResult.DRAW)}, White wins: {results.count(CheckersResult.WHITE_WINS)}, Black wins: {results.count(CheckersResult.BLACK_WINS)}")
    file.write(f"Average time: {sum(times)/len(times)}, minimum time: {min(times)}, max time: {max(times)}\n")
    file.write(f"Average number of moves: {sum(number_of_moves)/len(number_of_moves)}\n")
    file.write(f"Draw: {results.count(CheckersResult.DRAW)}, White wins: {results.count(CheckersResult.WHITE_WINS)}, Black wins: {results.count(CheckersResult.BLACK_WINS)}\n")
    file.close()
if __name__ == "__main__":
    main()

# Generate prof:  python3 -m cProfile -o main.prof main.py
# Visualise prof: snakeviz main.prof