from enums import (
    CheckersResult,
    CheckersRules,
    CheckersSquare,
    CheckersPlayer,
    MoveType
)

import traceback
import itertools
from typing import List, Dict
from copy import deepcopy, copy
from unitary.alpha import QuantumObject, QuantumWorld, quantum_if, Move, Split, Flip
from unitary.alpha.qudit_effects import QuditFlip
import unitary.alpha as alpha
from math import ceil
from quantum_split import CheckersSplit, CheckersClassicMove
from unitary.alpha.qudit_gates import QuditXGate, QuditISwapPowGate

# from cirq import ISWAP
import cirq
import random
import numpy as np

# GLOBAL GAME SETTINGS
_forced_take = True
_MARK_SYMBOLS = {CheckersSquare.EMPTY: ".", CheckersPlayer.WHITE: "w", CheckersPlayer.BLACK: "b"}

def _histogram(num_vertical, num_horizontal, results: List[List[CheckersSquare]]) -> List[Dict[CheckersSquare, int]]:
    """Turns a list of whole board measurements into a histogram.

    Returns:
        A num_horizontal*num_vertical element list (one for each square) that contains a dictionary with
        counts for EMPTY, X, and O.
    """
    hist = []
    for idx in range(num_vertical*num_horizontal):
        hist.append({CheckersSquare.EMPTY: 0, CheckersSquare.FULL: 0})
    for r in results:
        for idx in range(num_vertical*num_horizontal):
            hist[idx][r[idx]] += 1
    return hist

class Move_id:
    """
    Logic for doing moves using ids
    """
    def __init__(self, movetype: MoveType, player: CheckersPlayer, source_id: int, target1_id: int, target2_id: int = None) -> None:
        self.movetype = movetype
        self.player = player
        self.source_id = source_id
        self.target1_id = target1_id
        self.target2_id = target2_id
            
    def print_move(self, index = -1) -> None:
        output = f"({self.player.name}, {self.movetype.name}) "
        if(index != -1):
            output = str(index) + ": "
        output += f"[{self.source_id}] to [{self.target1_id}]"
        if(self.target2_id != None):
            output += f" and [{self.target2_id}]"
        print(output)
        return output
    
    def get_move(self, index = -1) -> None:
        output = f"({self.player.name}, {self.movetype.name}) "
        if(index != -1):
            output = str(index) + ": "
        output += f"[{self.source_id}] to [{self.target1_id}]"
        if(self.target2_id != None):
            output += f" and [{self.target2_id}]"
        return output

class Move_temp:
    def __init__(self, source_x: int, source_y: int, target1_x: int, target1_y: int, target2_x: int = None, target2_y: int = None) -> None:
        self.source_x = source_x
        self.source_y = source_y
        self.target1_x = target1_x
        self.target1_y = target1_y
        self.target2_x = target2_x
        self.target2_y = target2_y

    def print_move(self, index = -1) -> None:
        output = ""
        if(index != -1):
            output = str(index) + ": "
        output += f"[{self.source_x}, {self.source_y}] to [{self.target1_x}, {self.target1_y}]"
        if(self.target2_x != None):
            output += f" and [{self.target2_x}, {self.target2_y}]"
        print(output)

class Piece():
    def __init__(self, id: int, color: CheckersPlayer, king: bool = False, superposition: bool = False, chance:float = 100) -> None:
        self.id = id
        self.color = color
        self.king = king
        self.superposition = superposition
        self.chance = chance

class Entangled():
    def __init__(self, related_squares: list, is_taken: str, not_taken: str, successfully_takes: str, unsuccessfully_takes: str) -> None:
        self.all_ids = related_squares # All ids
        self.is_taken = is_taken # The piece that is being taken by another piece which causes entanglement
        self.not_taken = not_taken # The pieces that are related to the piece that is taken
        self.successfully_takes = successfully_takes # The piece that is (maybe) successfull in taking another piece
        self.unsuccessfully_takes = unsuccessfully_takes # # The piece that was (maybe) unsuccessfull in taking another piece

    def update_entangled(self, org_id: str, new_ids: list):
        if(org_id in self.all_ids):
            self.all_ids.remove(org_id)
            self.all_ids += new_ids
    
    def measurement(self, id: str):
        """
        This function is called when a measurement is taking place. It returns all ids that are related to the id that is measured.
        """
        if(id in self.all_ids):
            return self.all_ids
        return []

class Checkers:
    def __init__(self, run_on_hardware = False, num_vertical = 5, num_horizontal = 5, num_vertical_pieces = 1, rules = CheckersRules.QUANTUM_V3, SIMULATE_QUANTUM = False) -> None:
        self.rules = rules
        self.SIMULATE_QUANTUM = False
        if(SIMULATE_QUANTUM.lower() == "true"):
            self.SIMULATE_QUANTUM = True
        self.player = CheckersPlayer.WHITE
        self.num_vertical = num_vertical
        self.run_on_hardware = run_on_hardware
        self.num_horizontal = num_horizontal
        self.num_vertical_pieces = num_vertical_pieces # how many rows of one color need to be filled with pieces
        self.classical_squares = {} # Contains information about a square (e.g. white, king, etc...)
        self.related_squares = [] # List of lists that keep track of squares in superpositions that are related to each other. This way if a square is measured we know the related squares of that square
        self.q_rel_moves = [] # parallel to related squares, but keeps track of quantum moves
        self.q_moves = [] # Just a list of al quantum moves so we can do them again when doing a new move
        self.entangled_squares = [] # list of squares that have been jumped over causing entanglement
        self.related_entangled_squares = [] # Total list of squares that are related to the entangled square
        self.entangled_objects = [] # list of entangled objects
        self.white_squares = {}
        self.black_squares = {}
        self.status = CheckersResult.UNFINISHED
        self.superposition_pieces = set() # contains a list of pieces that started the superposition. This is needed to recreate the board when a move has been done
        self.moves_since_take = 0 # Number of moves since a piece has been taken
        if(num_vertical_pieces*2 >= num_vertical):
            print(f"Too many rows ({num_vertical_pieces}) filled with pieces. Decrease this number for this size of board. [{num_vertical}]x[{num_horizontal}]")
            exit()
        # Initialize empty board
        self.clear()
        # Add initial pieces to board
        king = False
        for y in range(self.num_vertical):
            for x in range(self.num_horizontal):
                if(x % 2 == 1 and y % 2 == 0 or x % 2 == 0 and y % 2 == 1):
                    id = self.convert_xy_to_id(x, y)
                    if(y <= self.num_vertical_pieces-1): # We are in the beginning rows, initialize black
                        if(not self.SIMULATE_QUANTUM):
                            QuditFlip(2, 0, CheckersSquare.FULL.value)(self.squares[str(id)]) # Black
                        self.classical_squares[str(id)] = Piece(str(id), CheckersPlayer.BLACK, king)
                    elif(y >= self.num_vertical - self.num_vertical_pieces):
                        if(not self.SIMULATE_QUANTUM):
                            QuditFlip(2, 0, CheckersSquare.FULL.value)(self.squares[str(id)]) # White
                        self.classical_squares[str(id)] = Piece(str(id), CheckersPlayer.WHITE, king)
        self.legal_moves = self.calculate_possible_moves(self.player)

    def write_to_log(self, string):
        self.log = open("./log.txt", "a")
        self.log.write(string)
        self.log.close()

    def measure_square(self, id) -> CheckersSquare:
        """
        Measures single square and returns CheckersSquare.EMPTY or CheckersSquare.FULL for ID
        """
        all_ids = self.remove_from_rel_entangled_squares(id)
        for ids in all_ids:
            # Check out all ids, for the one that remained, remove all others from classical squares
            if(not self.SIMULATE_QUANTUM):
                for classical_id in ids:
                    self.board.pop(objects=[self.squares[str(classical_id)]])
                    # original_peek = (self.board.peek(objects=[self.squares[str(id)]])) # peek returns double list of all object peeked. For one object that looks like [[<CheckersSquare.WHITE: 1>]]
                    peek = (self.board.peek(objects=[self.squares[str(classical_id)]]))
                    if(peek[0][0] == CheckersSquare.FULL):
                        self.classical_squares[str(classical_id)].chance = 100
                        for i in self.entangled_squares: 
                            if(str(classical_id) in i): # If the piece is in the entangled squares it has been jumped over and needs to be removed
                                self.remove_piece(str(classical_id), True)
                                self.entangled_squares.remove(i)
                                continue
                        continue
                    self.remove_piece(str(classical_id))
                return(self.board.peek(objects=[self.squares[str(id)]])[0][0]) # returns for original id
            else: # If we are only simulating
                # First select the id that remains
                if(len(ids) == 0): # If its is a classical piece
                    return CheckersSquare.FULL
                idx = random.randint(0, len(ids)-1)
                # try:
                self.classical_squares[str(ids[idx])].chance = 100
                # except Exception as error:
                #     print("ERROR")
                #     print(traceback.format_exc())
                #     print(ids)
                #     print(self.classical_squares.keys())
                #     exit()
                for i, classical_id in enumerate(ids):
                    if(i == idx):
                        continue
                    self.remove_piece(str(classical_id))                
                return CheckersSquare.FULL if str(ids[idx]) == str(id) else CheckersSquare.EMPTY

    def on_board(self, x, y):
        """
        Checks if given location is on the board on not. 
        Returns true if [x][y] is on the board
        """
        if(x < 0 or x > self.num_horizontal-1 or y < 0 or y > self.num_vertical-1):
            return False
        return True

    def get_advanced_positions(self, player: CheckersPlayer):
        white_pieces = {}
        black_pieces = {}
        for key, value in self.classical_squares.items():
            id = str(key)
            if(value.color == CheckersPlayer.WHITE):
                white_pieces[id] = value
            else:
                black_pieces[id] = value
        return (white_pieces, black_pieces) if (player == CheckersPlayer.WHITE) else (black_pieces, white_pieces)

    def get_positions(self, player: CheckersPlayer):
        """
        Returns player_ids: [normal pieces, king pieces], opponent_ids: [normal pieces, king pieces]
        player_ids and opponent_ids contain the ids of the current player and other player
        Returns 2 2d list that contain normal ids and king ids
        """
        white_ids = []
        white_king_ids = []
        black_ids = []
        black_king_ids = []
        for key, value in self.classical_squares.items():
            id = int(key)
            if(value.color == CheckersPlayer.WHITE):
                white_king_ids.append(id) if (value.king) else white_ids.append(id)
            else:
                black_king_ids.append(id) if(value.king) else black_ids.append(id)
        if(player == CheckersPlayer.WHITE):
            return [white_ids, white_king_ids], [black_ids, black_king_ids]
        else:
            return [black_ids, black_king_ids], [white_ids, white_king_ids]

    def calculate_possible_moves(self, player: CheckersPlayer = None) -> list:
        """
        Calculates all possible moves for 'player'
        Loop over all pieces, if there is a chance that there is a piece in the right color calculate legal moves for that piece
        Returns true if the player can take another piece
        """
        legal_moves = [] # All legal moves
        legal_take_moves = [] # Only the moves which can take another player
        if(player == None):
            player = self.player
        player_ids, opponent_ids = self.get_positions(player)
        blind_moves = []
        for id in player_ids[0]: #all normal ids
            blind_moves += self.calculate_blind_moves(id, player, False)
        for id in player_ids[1]:
            blind_moves += self.calculate_blind_moves(id, player, True)
        # Append all ids to one list'
        player_ids = player_ids[0] + player_ids[1]
        opponent_ids = opponent_ids[0] + opponent_ids[1]
        for move in blind_moves:
            # For each move check if there is a piece in the position
            # If it is empty it is a legal move
            # If there is another piece, check if it is a different color than your own color
            # If so, check if one square further is empty
            # If so you can take a piece
            source_id = self.convert_xy_to_id(move.source_x, move.source_y)
            target1_id = self.convert_xy_to_id(move.target1_x, move.target1_y)
            target2_id = None
            if(move.target2_x != None):
                target2_id = self.convert_xy_to_id(move.target2_x, move.target2_y)
            # CLASSICAL MOVE   
            if(target1_id not in player_ids and target1_id not in opponent_ids and target2_id == None): # it is an empty square, so it is possible move there
                legal_moves.append(Move_id(MoveType.CLASSIC, self.player, source_id, target1_id))
            
            # QUANTUM SPLIT MOVE
            elif(target1_id not in player_ids and target1_id not in opponent_ids and target2_id not in player_ids and target2_id not in opponent_ids):
                legal_moves.append(Move_id(MoveType.SPLIT, self.player, source_id, target1_id, target2_id))

            # CLASSICAL TAKE MOVE
            elif(target1_id in opponent_ids and target2_id == None): # There is an opponent in this coordinate, check if we can jump over them
                jump_y = move.target1_y+(move.target1_y-move.source_y)
                jump_x = move.target1_x+(move.target1_x-move.source_x)
                jump_id = self.convert_xy_to_id(jump_x, jump_y)
                if(self.on_board(jump_x, jump_y) and jump_id not in (player_ids+opponent_ids)): # we can jump over if the coordinates are on the board and the piece is empty
                    move_type = MoveType.TAKE
                    if(self.classical_squares[str(source_id)].chance == 100 and self.classical_squares[str(target1_id)].chance < 100):
                        move_type = MoveType.ENTANGLE
                    
                    legal_moves.append(Move_id(move_type, self.player, source_id, jump_id))
                    legal_take_moves.append(Move_id(move_type, self.player, source_id, jump_id))

        if(len(legal_take_moves) != 0 and _forced_take): # If we can take a piece and taking a piece is forced, return only the moves that can take a piece
            return legal_take_moves
        return legal_moves
    
    def calculate_blind_moves(self, id: int, player: CheckersPlayer, king: bool = False):
        """
        For the piece in id, that belongs to player, calculate all 'possible' moves ignoring other pieces, but checking for boundaries of the board
        Important: Assumes there is a piece in the position of the id that belongs to the current player
        """
        x, y = self.convert_id_to_xy(int(id))
        blind_moves = []
        if player == CheckersPlayer.WHITE and not king: # White moves up -> y-1
            left = False
            right = False
            if(self.on_board(x-1, y-1)):
                blind_moves.append(Move_temp(x,y,x-1,y-1))
                left = True
            if(self.on_board(x+1, y-1)):
                blind_moves.append(Move_temp(x,y,x+1,y-1))
                right = True
            if(left and right and self.rules.value > CheckersRules.CLASSICAL.value):
                blind_moves.append(Move_temp(x,y,x-1,y-1,x+1,y-1))
        elif player == CheckersPlayer.BLACK and not king: # Black piece that moves down -> y+1
            left = False
            right = False
            if(self.on_board(x-1, y+1)):
                blind_moves.append(Move_temp(x,y,x-1,y+1))
                left = True
            if(self.on_board(x+1, y+1)):
                blind_moves.append(Move_temp(x,y,x+1,y+1))
                right = True
            if(left and right and self.rules.value > CheckersRules.CLASSICAL.value):
                blind_moves.append(Move_temp(x,y,x-1,y+1,x+1,y+1))
        else: # King piece that can move in all for directions
            bottom_left, bottom_right, top_left, top_right = False, False, False, False
            if(self.on_board(x-1, y-1)):
                blind_moves.append(Move_temp(x,y,x-1,y-1))
                top_left = True
            if(self.on_board(x+1, y-1)):
                blind_moves.append(Move_temp(x,y,x+1,y-1))
                top_right = True
            if(self.on_board(x-1, y+1)):
                blind_moves.append(Move_temp(x,y,x-1,y+1))
                bottom_left = True
            if(self.on_board(x+1, y+1)):
                blind_moves.append(Move_temp(x,y,x+1,y+1))
                bottom_right = True
            # TODO: fix this mess, currently checking all possible combinations. Can probably be done more optimally.
            if(self.rules.value == CheckersRules.CLASSICAL.value):
                return blind_moves
            if(top_left):
                if(top_right):
                    blind_moves.append(Move_temp(x,y,x-1,y-1,x+1,y-1))
                if(bottom_left):
                    blind_moves.append(Move_temp(x,y,x-1,y-1,x-1,y+1))
                if(bottom_right):
                    blind_moves.append(Move_temp(x,y,x-1,y-1,x+1,y+1))
            if(top_right):
                if(bottom_left):
                    blind_moves.append(Move_temp(x,y,x+1,y-1,x-1,y+1))
                if(bottom_right):
                    blind_moves.append(Move_temp(x,y,x+1,y-1,x+1,y+1))
            if(bottom_left and bottom_right):
                blind_moves.append(Move_temp(x,y,x-1,y+1,x+1,y+1))
        return blind_moves
    
    def alternate_classic_move(self):
        """
        Instead of doing a normal classic move, creates a new board, this is done to increase performance
        """
        # First do quantum moves
        q_ids = list(itertools.chain.from_iterable(self.related_squares))
        for id in range(self.num_vertical*self.num_horizontal):
            self.squares[str(id)] = QuantumObject(str(id), CheckersSquare.EMPTY)

        # for each sequence of quantum moves, we have to initialize the first bit that starts the qm. # THIS DOESNT WORK IF TWO QUANTUM MOVES START FROM THE SAME POSITION
        temp = []
        for qm in self.q_rel_moves: # Temporary disabled
            # self.squares[str(qm[0].source_id)] = QuantumObject(str(qm[0].source_id), CheckersSquare.FULL)
            temp.append(qm[0].source_id)
        # A quantumworld must first exist before we can do the quantum moves
        self.board = QuantumWorld(
            list(self.squares.values()),  compile_to_qubits=self.run_on_hardware
        )
        index = 0
        for qm in self.q_moves:
            # print(self.q_rel_moves[index][0], qm)
            # print(type(self.q_rel_moves[index][0]), type(qm))
            # print((self.q_rel_moves[index][0] == qm))
            if(index <= len(self.q_rel_moves)-1 and self.q_rel_moves[index][0] == qm): # IF IT IS THE FIRST MOVE IN THE SEQUENCE OF QUANTUM MOVES IT NEEDS TO BE INITIALIZED
                index += 1
                QuditFlip(2, 0, CheckersSquare.FULL.value)(self.squares[str(qm.source_id)])
                # print("TRUE #######################################################################################################################")
            if(qm.movetype == MoveType.SPLIT):
                CheckersSplit(CheckersSquare.FULL, self.rules)(self.squares[str(qm.source_id)], self.squares[str(qm.target1_id)], self.squares[str(qm.target2_id)])
            elif(qm.movetype == MoveType.ENTANGLE):
                # If we entangle we also need to initalize the first bit
                QuditFlip(2, 0, CheckersSquare.FULL.value)(self.squares[str(qm.source_id)])
                _, jumped_id = self.is_adjacent(qm.source_id, qm.target1_id)
                alpha.quantum_if(self.squares[str(jumped_id)]).equals(CheckersSquare.FULL).apply(CheckersClassicMove(2, 1))(self.squares[str(qm.source_id)], self.squares[str(qm.target1_id)])
            else:
                CheckersClassicMove(2, 1)(self.squares[str(qm.source_id)], self.squares[str(qm.target1_id)])
        
        for id in range(self.num_vertical*self.num_horizontal):
            if(str(id) in self.classical_squares and str(id) not in q_ids): # If there is a piece that is not in superposition
                QuditFlip(2, 0, CheckersSquare.FULL.value)(self.squares[str(id)])

    def create_new_filled_board(self):
        """
        Creates new board with the values in self.squares
        """
        self.board = QuantumWorld(
            list(self.squares.values()), compile_to_qubits=self.run_on_hardware
        )
    
    def clear(self):
        """
        Create empty the board
        """
        self.squares = {}
        self.king_squares = {}
        self.white_squares = {}
        self.black_squares = {}
        self.classical_squares = {}

        for i in range(self.num_vertical*self.num_horizontal):
            self.squares[str(i)] = QuantumObject(str(i), CheckersSquare.EMPTY)
        self.board = QuantumWorld(
            list(self.squares.values()), compile_to_qubits=self.run_on_hardware
        )

    def player_move(self, move: Move_id, player: CheckersPlayer = None):
        self.moves_since_take += 1
        prev_taken = False
        to_king = [] # list that holds moved pieces to check if they need to be kinged
        if(player == None):
            player = self.player
        if(move.target2_id == None):
            prev_taken, failed = self.classic_move(move)
            if(prev_taken):
                self.moves_since_take = 0
            if(not failed):
                to_king.append(move.target1_id)
        else:
            # if not classical move it is a split move
            self.split_move(move)
            to_king.append(move.target1_id)
            to_king.append(move.target2_id)
        
        for id in to_king:
            _, y = self.convert_id_to_xy(id)
            if((y == self.num_vertical-1 or y == 0) and self.classical_squares[str(id)].king == False):
                self.king(id)

        # If a move has been done we need to flip the player, IF they can not take another piece with the piece just used
        can_take, legal_moves = self.can_take_piece(move.target1_id)
        if(prev_taken and can_take): # If we took a piece and we can take another piece do not chance the player
            self.legal_moves = legal_moves
            return
        self.player = CheckersPlayer.BLACK if self.player == CheckersPlayer.WHITE else CheckersPlayer.WHITE
        self.legal_moves = self.calculate_possible_moves(self.player)
        self.status = self.result()

    def get_board(self) -> str:
        """Returns the Checkers board in ASCII form. Also returns dictionary with id as key.
        Function take from quantum tiq taq toe"""
        results = self.board.peek(count=100)
        hist = _histogram(self.num_vertical, self.num_horizontal,
            [
                [CheckersSquare.from_result(square) for square in result]
                for result in results
            ]
        )
        output = "\n"
        try: # Try except will be removed later, was used for debugging inconsistencies between quantum state and classical states
            for y in range(self.num_vertical):
                for mark in [CheckersSquare.EMPTY, CheckersPlayer.WHITE, CheckersPlayer.BLACK]:
                    output += " "
                    for x in range(self.num_horizontal):
                        idx = self.convert_xy_to_id(x,y)
                        if(x % 2 == 0 and y % 2 == 0 or x % 2 == 1 and y % 2 == 1):
                            output += " "
                            output += f"-"*5
                        elif(mark == CheckersSquare.EMPTY):
                            output += f" . {hist[idx][CheckersSquare.EMPTY]:3}"
                        elif(mark == CheckersPlayer.WHITE):
                            identifier = "w"
                            if(hist[idx][CheckersSquare.FULL] > 0 and self.classical_squares[str(idx)].color == CheckersPlayer.WHITE):
                                if(self.classical_squares[str(idx)].king):
                                    identifier = "W"
                                output += f" {identifier} {hist[idx][CheckersSquare.FULL]:3}"
                            else:
                                output += f" {identifier} {0:3}"
                        else:
                            identifier = "b"
                            if(hist[idx][CheckersSquare.FULL] > 0 and self.classical_squares[str(idx)].color == CheckersPlayer.BLACK):
                                if(self.classical_squares[str(idx)].king):
                                    identifier = "B"
                                output += f" {identifier} {hist[idx][CheckersSquare.FULL]:3}"
                            else:
                                output += f" {identifier} {0:3}"
                        if x != self.num_horizontal-1:
                            output += " |"
                    output += "\n"
                if y != self.num_vertical-1:
                    output += "--------"*self.num_horizontal + "\n"
        except Exception as error:
            print(traceback.format_exc())
            print(f"ERROR: {error}")
            output = "Quantum moves: "
            for i in self.q_moves:
                output += i.get_move()
                output+= " --- "
            print(output)
            output = "Quantum relative moves"
            for qm in self.q_rel_moves:
                output += "["
                for m in qm:
                    output += m.get_move()
                    output += ", "
                output += "] --- "
            print(output)
            print(f"Classical squares: {self.classical_squares.keys()}")
            print(f"Chance is {hist[idx][CheckersSquare.FULL]} for id {idx}")
            exit()
        return output
    
    def get_sim_board(self) -> str:
        """Returns the simulated Checkers board in ASCII form. Also returns dictionary with id as key.
        Function take from quantum tiq taq toe"""
        # results = self.board.peek(count=100)
        # hist = _histogram(self.num_vertical, self.num_horizontal,
        #     [
        #         [CheckersSquare.from_result(square) for square in result]
        #         for result in results
        #     ]
        # )
        output = "\n"
        try: # Try except will be removed later, was used for debugging inconsistencies between quantum state and classical states
            for y in range(self.num_vertical):
                for mark in [CheckersSquare.EMPTY, CheckersPlayer.WHITE, CheckersPlayer.BLACK]:
                    output += " "
                    for x in range(self.num_horizontal):
                        idx = self.convert_xy_to_id(x,y)
                        if(x % 2 == 0 and y % 2 == 0 or x % 2 == 1 and y % 2 == 1):
                            output += " "
                            output += f"-"*5
                        elif(mark == CheckersSquare.EMPTY):
                            if(str(idx) not in self.classical_squares.keys()):
                                output += f" . {100:3}"
                            else:
                                output += f" . {0:3}"
                        elif(mark == CheckersPlayer.WHITE):
                            identifier = "w"
                            if(str(idx) in self.classical_squares.keys() and self.classical_squares[str(idx)].color == CheckersPlayer.WHITE):
                                if(self.classical_squares[str(idx)].king):
                                    identifier = "W"
                                output += f" {identifier} {int(self.classical_squares[str(idx)].chance):3}"
                            else:
                                output += f" {identifier} {0:3}"
                        else:
                            identifier = "b"
                            if(str(idx) in self.classical_squares.keys() and self.classical_squares[str(idx)].color == CheckersPlayer.BLACK):
                                if(self.classical_squares[str(idx)].king):
                                    identifier = "B"
                                output += f" {identifier} {int(self.classical_squares[str(idx)].chance):3}"
                            else:
                                output += f" {identifier} {0:3}"
                        if x != self.num_horizontal-1:
                            output += " |"
                    output += "\n"
                if y != self.num_vertical-1:
                    output += "--------"*self.num_horizontal + "\n"
        except Exception as error:
            print(traceback.format_exc())
            print(f"ERROR: {error}")
            output = "Quantum moves: "
            for i in self.q_moves:
                output += i.get_move()
                output+= " --- "
            print(output)
            output = "Quantum relative moves"
            for qm in self.q_rel_moves:
                output += "["
                for m in qm:
                    output += m.get_move()
                    output += ", "
                output += "] --- "
            print(output)
            print(f"Classical squares: {self.classical_squares.keys()}")
            exit()
        return output

    def king(self, id: int):
        self.classical_squares[str(id)].king = True
        return

    def is_adjacent(self, id1, id2):
        """
        Checks if id1 is adjacent to id2 (one of the eight squares surrounding it)
        Returns true if id1 and id2 are adjacent
        Returns false and the jumped over id if id1 and id2 are not adjacent
        """
        if(id1 < 0 or id1 > self.num_horizontal*self.num_vertical-1 or id2 < 0 or id2 > self.num_horizontal*self.num_vertical-1):
            return False
        x1, y1 = self.convert_id_to_xy(id1)
        x2, y2 = self.convert_id_to_xy(id2)
        if(abs(x1-x2) > 1 or abs(y1-y2) > 1):
            if(abs(x1-x2) == 2 and abs(y1-y2) == 2):
                return False, self.convert_xy_to_id(max(x1, x2)-1, max(y1, y2)-1)
            return False, None
        return True, None

    def can_take_piece(self, id):
        """
        For a specific ID, checks if it can take pieces. Used for checking if you can take another piece after taking a piece
        Returns true and the possible moves this piece can do if this piece can take a piece
        """
        blind_moves = self.calculate_blind_moves(id, self.player)
        player_ids, opponent_ids = self.get_positions(self.player)
        
        # Concatenate all normal pieces and king pieces
        player_ids = player_ids[0] + player_ids[1]
        opponent_ids = opponent_ids[0] + opponent_ids[1]
        legal_moves = []
        for move in blind_moves:
            target1_id = self.convert_xy_to_id(move.target1_x, move.target1_y)
            if(target1_id in opponent_ids and move.target2_x == None):                
                jump_y = move.target1_y+(move.target1_y-move.source_y)
                jump_x = move.target1_x+(move.target1_x-move.source_x)
                jump_id = self.convert_xy_to_id(jump_x, jump_y)
                if(self.on_board(jump_x, jump_y) and jump_id not in (player_ids+opponent_ids)): # we can jump over if the coordinates are on the board and the piece is empty
                    legal_moves.append(Move_id(MoveType.TAKE, self.player, id, jump_id))
        if(len(legal_moves) > 0):
            return True, legal_moves
        return False, []

    def return_all_possible_states(self, move: Move_id):
        """
        This function returs all possible states/outcomes for a specific move
        """
        if(move.movetype != MoveType.TAKE):
            # raise RuntimeError(f"Not a take move: [{move.source_id} to {move.target1_id}]")
            return [], []
        _, jumped_id = self.is_adjacent(move.source_id, move.target1_id)
        source_ids = self.get_rel_squares(move.source_id)
        jumped_ids = self.get_rel_squares(jumped_id)
        states = []
        weights = []
        for sid in source_ids:
            checked = False
            for jid in jumped_ids:
                # temp_state = deepcopy(new_state)
                temp_state = Sim_Checkers(run_on_hardware=False, num_vertical=self.num_vertical, num_horizontal=self.num_horizontal, num_vertical_pieces=self.num_vertical_pieces, classical_squares=deepcopy(self.classical_squares), related_squares=deepcopy(self.related_squares), q_rel_moves=deepcopy(self.q_rel_moves), q_moves=deepcopy(self.q_moves), superposition_pieces=deepcopy(self.superposition_pieces), status=deepcopy(self.status), moves_since_take=deepcopy(self.moves_since_take), king_squares=deepcopy(self.king_squares), legal_moves=deepcopy(self.legal_moves), rules=self.rules)
                if(sid == str(move.source_id) and jid == str(jumped_id)): # State where a piece is actually taken.
                    # Weight is chance that sid is there times chance that jid is there
                    weights.append(self.classical_squares[str(sid)].chance/100 * self.classical_squares[str(jid)].chance/100)
                    temp_state.remove_piece(jumped_id, False)
                    jumped_ids = temp_state.remove_from_rel_squares(jumped_id)
                    # for i, classical_id in enumerate(ids):

                    temp_state.classical_squares[str(move.source_id)].chance = 100
                    temp_state.classical_squares[str(move.target1_id)] = temp_state.classical_squares[str(move.source_id)]
                    temp_state.classical_squares[str(move.target1_id)].id = move.target1_id
                    temp_state.remove_from_rel_squares(move.source_id)
                    temp_state.remove_piece(move.source_id)
                    for i in source_ids:
                        if(i == str(move.source_id)):
                            continue
                        temp_state.remove_piece(str(i))
                    
                    for j in jumped_ids:
                        if(j == str(jid)):
                            continue
                        temp_state.remove_piece(str(j))
                    temp_state.legal_moves = temp_state.calculate_possible_moves(self.player)
                    states.append(temp_state)

                elif(sid == str(move.source_id) and jid != str(jumped_id)): # Only the original piece is there, and when we measure the other piece is not there.             
                    # Weight is chance that sid is there times chance that jid is not there
                    weights.append(self.classical_squares[str(sid)].chance/100 * self.classical_squares[str(jid)].chance/100)
                    temp_state.classical_squares[str(sid)].chance = 100
                    temp_state.classical_squares[str(jid)].chance = 100
                    
                    for i in source_ids:
                        if(i == str(move.source_id)):
                            continue
                        temp_state.remove_piece(str(i))
                    temp_state.remove_from_rel_squares(sid)

                    for j in jumped_ids:
                        if(j == str(jid)):
                            continue
                        temp_state.remove_piece(str(j))
                    
                    temp_state.remove_from_rel_squares(jid)
                    temp_state.legal_moves = temp_state.calculate_possible_moves(self.player)
                    states.append(temp_state)
                elif(not checked): # The original piece isn't there, therefore we do not measure the jumped piece. This only needs to be checked for every sid
                    # weights is chance that sid is there
                    weights.append(self.classical_squares[str(sid)].chance/100)
                    checked = True
                    temp_state.classical_squares[str(sid)].chance = 100
                    for i in source_ids:
                        if(i == str(sid)):
                            continue
                        temp_state.remove_piece(str(i))
                    temp_state.remove_from_rel_squares(sid)
                    temp_state.legal_moves = temp_state.calculate_possible_moves(self.player)
                    states.append(temp_state)
        # print(f"LEN STATE: {len(states)}")
        # for i in (states):
        #     print("BOARD")
        #     print(i.get_sim_board())
        return states, weights

    def classic_move(self, move: Move_id) -> [bool, bool]:
        """
        This function moves a piece from one square to another. If it jumps over a piece it also removes this piece.
        It also measures the piece itself or the piece it is taking if it is relevant.
        Returns two booleans. First one is true if a piece has been taken. Second one is true if a move has failed
        """
        # states, weights = self.return_all_possible_states(move)
        # for i in states:
        #     print(i.get_sim_board())
        # print(weights)
        taken = False # To return if the move took a piece or not
        is_adjacent, jumped_id = self.is_adjacent(move.source_id, move.target1_id)
        if(not is_adjacent): # if ids are not adjacent we jumped over a piece and need to remove it
            if(self.rules.value <= CheckersRules.QUANTUM_V1.value or (not(self.classical_squares[str(move.source_id)].chance == 100 and self.classical_squares[str(jumped_id)].chance < 100))): # If a the source piece is in superposition
                # First check if the piece we are using is actually there
                if(self.measure_square(move.source_id) == CheckersSquare.EMPTY): # If the piece is not there, turn is wasted
                    self.remove_piece(move.source_id)
                    return taken, True

                # Next check if the piece we are taking is actually there
                if(self.measure_square(jumped_id) == CheckersSquare.EMPTY): # if it empty our turn is wasted
                    # CHECK IF PIECE WAS ENTANGLED
                    # for count, i in enumerate(self.entangled_squares): # If we have jumped over a piece and it is entangled, we need to remove the piece it is entangled with
                    #     print(i)
                    #     for j in i:
                    #         if(j == jumped_id):
                    #             entangled = count
                    #             print("ENTANGLED")
                    #             break
                    # if(entangled != -1):
                    #     for i in self.entangled_squares[entangled]:
                    #         self.remove_piece(i, True)
                    #         self.remove_id_from_rel_squares(i)
                    #         taken = True
                    # else:
                    self.remove_piece(jumped_id) # We still measured so we have to remove it from the classical squares list
                    return taken, True
                              
                self.remove_piece(jumped_id, True)
                self.remove_id_from_rel_squares(jumped_id)
                taken = True
            else: # ENTANGLEMENT. ALWAYS JUMPS OVER SUPERPOSITION PIECES
                alpha.quantum_if(self.squares[str(jumped_id)]).equals(CheckersSquare.FULL).apply(CheckersClassicMove(2, 1))(self.squares[str(move.source_id)], self.squares[str(move.target1_id)])
                original_piece = self.classical_squares[str(move.source_id)]
                
                self.classical_squares[str(move.target1_id)] = Piece(id=str(move.target1_id), color=original_piece.color, king=original_piece.king, superposition=True)

                # Since we jump over a piece in superposition we need to add these two pieces to the correct superposition squares in related squares
                self.classical_squares[str(move.target1_id)].chance = self.classical_squares[str(jumped_id)].chance
                self.classical_squares[str(move.source_id)].chance = 100-self.classical_squares[str(jumped_id)].chance
                self.entangled_squares.append([str(jumped_id)])
                for i, rel_squares in enumerate(self.related_squares):
                    if(str(jumped_id) in rel_squares):
                        related_entangled_squares = deepcopy(rel_squares)
                        related_entangled_squares.append(str(move.target1_id))
                        related_entangled_squares.append(str(move.source_id))
                        # rel_squares.append(str(move.source_id))
                        # rel_squares.append(str(move.target1_id))
                        self.related_entangled_squares.append(related_entangled_squares)
                        temp_list = deepcopy(rel_squares)
                        temp_list.remove(str(jumped_id))
                        self.entangled_objects.append(Entangled(related_entangled_squares, str(jumped_id), temp_list, str(move.target1_id), str(move.source_id)))
                        self.q_rel_moves[i].append(move)
                        self.q_moves.append(move)
                self.superposition_pieces.add(original_piece)
                return taken, False
                # CheckersSplit(CheckersSquare.FULL, self.rules)(self.squares[str(move.source_id)], self.squares[str(move.target1_id)], self.squares[str(move.target2_id)])
        self.classical_squares[str(move.target1_id)] = self.classical_squares[str(move.source_id)]
        self.classical_squares[str(move.target1_id)].id = move.target1_id
        # If we do a classical move on a piece in superposition, we need to append the new id to the correct list in related_squares
        for i, squares in enumerate(self.related_squares):
            if(str(move.source_id) in squares):
                squares.append(str(move.target1_id))
                self.q_rel_moves[i].append(move)
                self.q_moves.append(move)
                break
        
        for i, squares in enumerate(self.related_entangled_squares):
            if(str(move.source_id) in squares):
                squares.append(str(move.target1_id))
                squares.remove(str(move.source_id))
                break

        # If we do a classical move on a piece that is entangled, we need to append the new id to the correct entangled list
        for i, squares in enumerate(self.entangled_squares):
            if(str(move.source_id) in squares):
                squares.append(str(move.target1_id))
                # self.q_rel_moves[i].append(move)
                # self.q_moves.append(move)
                squares.remove(str(move.source_id))

        # self.concat_moves(move, move.source_id) # EXPERIMENTAL
        # The piece moved so we need to cleanup the original id
        self.remove_id_from_rel_squares(move.source_id)
        self.remove_piece(move.source_id)
        if(not self.SIMULATE_QUANTUM):
            self.alternate_classic_move()
        return taken, False
    
    def split_move(self, move: Move_id):
        if(move.target2_id == None):
            raise ValueError("No second target given")
        original_piece = self.classical_squares[str(move.source_id)]
        if(not self.SIMULATE_QUANTUM):
            CheckersSplit(CheckersSquare.FULL, self.rules)(self.squares[str(move.source_id)], self.squares[str(move.target1_id)], self.squares[str(move.target2_id)])
            # split = alpha.Split()
            # split(self.squares[str(move.source_id)], self.squares[str(move.target1_id)], self.squares[str(move.target2_id)])
        self.classical_squares[str(move.target1_id)] = Piece(id=str(move.target1_id), color=original_piece.color, king=original_piece.king, superposition=True)
        self.classical_squares[str(move.target2_id)] = Piece(id=str(move.target2_id), color=original_piece.color, king=original_piece.king, superposition=True)

        # If the piece was already in superposition, we need to append this piece to the list
        for i, squares in enumerate(self.related_squares):
            if(str(move.source_id) in squares):
                squares.append(str(move.target1_id))
                squares.append(str(move.target2_id))
                self.classical_squares[str(move.target1_id)].chance = original_piece.chance/2
                self.classical_squares[str(move.target2_id)].chance = original_piece.chance/2
                self.q_rel_moves[i].append(move)
                self.q_moves.append(move)
                break
        else: # Is executed if break was never called
            # If we get here this the first time this piece goes in superposition, so we add a new list
            self.classical_squares[str(move.target1_id)].chance = 50
            self.classical_squares[str(move.target2_id)].chance = 50
            self.related_squares.append([str(move.target1_id), str(move.target2_id)])
            self.q_rel_moves.append([move])
            self.q_moves.append(move)
            self.superposition_pieces.add(original_piece)

        for i, squares in enumerate(self.related_entangled_squares):
            if(str(move.source_id) in squares):
                squares.append(str(move.target1_id))
                squares.append(str(move.target2_id))
                squares.remove(str(move.source_id))
                break

        # if the piece was entangled, we need to append it to the correct list
        for i, squares in enumerate(self.entangled_squares):
            if(str(move.source_id) in squares):
                squares.append(str(move.target1_id))
                squares.append(str(move.target2_id))
                squares.remove(str(move.source_id))
                break
        self.remove_id_from_rel_squares(move.source_id)
        self.remove_piece(move.source_id)
        return       

    def remove_piece(self, id: int or (int,int), flip = False):
        """
        Removes a piece from the classical_squares list. If flip is true it will also flip the quantum state of that square.
        """
        if(type(id) is tuple):
            id = self.convert_xy_to_id(id[0], id[1])
        if(str(id) in self.classical_squares):
            self.classical_squares.pop(str(id))
            if(flip and not self.SIMULATE_QUANTUM):
                QuditFlip(2, CheckersSquare.FULL.value, CheckersSquare.EMPTY.value)(self.squares[str(id)])
        return
    
    def concat_moves(self, move, id): # used to concatenate a classical move after a split move to make it one split move
        """
        Experimental function to optimize the order of quantum moves when recreating the board.
        e.g.
            Split move: 1 -> 2 and 3
            Classic move: 3 -> 6
        Can be shortened by
            1 -> 2 and 6
        """
        
        
        # ID is the id that connect two moves. e.g. 21 -> 15 and 17; 15 -> 11
        # CANT OPTIMIZE IF
        # MOVE GOES BACK TO ORIGNAL SOURCE ID
        # MOVE GOES TO OTHER TARGET ID
        # Check if the id is in super position
        if(move.movetype != MoveType.CLASSIC):
            return
        temp_list = deepcopy(self.related_squares)
        for index, rel_squares in enumerate(temp_list):
            if(str(id) in rel_squares): # it is in super positionn
                for org_move in self.q_rel_moves[index]: # For all quantum moves that are related to the id 
                    if (org_move.target1_id == move.source_id and move.target1_id != org_move.source_id and move.target1_id != org_move.target2_id):
                        org_move.target1_id = move.target1_id
                        self.q_rel_moves[index].remove(move)
                        self.q_moves.remove(move)
                        return
                    if(org_move.target2_id == move.source_id and move.target1_id != org_move.source_id and move.target1_id != org_move.target1_id):
                        org_move.target2_id = move.target1_id
                        self.q_rel_moves[index].remove(move)
                        self.q_moves.remove(move)
                        return
        return

    def remove_id_from_rel_squares(self, id):
        """
        Removes one specific id from a list of superpositions..
        """
        # Check if the id we need to remove used to be in a superposition.
        temp_list = deepcopy(self.related_squares)
        for index, squares in enumerate(temp_list):
            if(str(id) in squares):
                i = self.related_squares[index].index(str(id)) # Get the index of the element we are removing
                self.related_squares[index].remove(str(id))
                
                if(len(self.related_squares[index]) <= 1): # If the length is one, we have returned to classical state (Basically if we did not just do a classical move)
                    self.related_squares.pop(index)
                    for mv in self.q_rel_moves[index]:
                        if(mv in self.q_moves):
                            self.q_moves.remove(mv)
                    self.q_rel_moves.pop(index)
                return

    def remove_from_rel_entangled_squares(self, id: str):
        """
        If an ID is measured, the ID itself and all related squares need to be removed
        """
        temp_list = deepcopy(self.related_entangled_squares)
        all_related_entangled_squares = []
        for index, squares in enumerate(temp_list):
            if(str(id) in squares):
                # If it is entangled we also need to remove from the related squares list
                self.remove_from_rel_squares(id)
                all_related_entangled_squares.append(self.related_entangled_squares.pop(index))
        return all_related_entangled_squares


    def remove_from_rel_squares(self, id):
        """
        If an ID is measured, the ID itself and all related squares need to be removed
        """
        temp_list = deepcopy(self.related_squares)
        for index, squares in enumerate(temp_list):
            if(str(id) in squares):
                for mv in self.q_rel_moves[index]:
                    if(mv in self.q_moves):
                        self.q_moves.remove(mv)
                self.q_rel_moves.pop(index)
                return self.related_squares.pop(index)
        return []
    
    def get_rel_squares(self, id):
        """
        Returns all related squares of an id
        """
        temp_list = deepcopy(self.related_squares)
        for index, squares in enumerate(temp_list):
            if(str(id) in squares):
                return self.related_squares[index]
        return [str(id)]
        
    def convert_xy_to_id(self, x, y) -> int:
        """
        x = horizontal (columns)
        y = vertical (rows)
        """
        return ((y*self.num_horizontal+x))
    
    def convert_id_to_xy(self, id: int) -> (int, int):
        return (id % self.num_horizontal, id // self.num_horizontal)

    def result(self):
        """
        returns:
            UNFINISHED = 0
            White wins = 1
            Black wins = 2
            DRAW = 3
            BOTH_WIN = 4
        """
        if(len(self.legal_moves) == 0):
            return CheckersResult.BLACK_WINS if self.player == CheckersPlayer.WHITE else CheckersResult.WHITE_WINS
        if(self.moves_since_take >= 40):
            return CheckersResult.DRAW
        return CheckersResult.UNFINISHED

class Sim_Checkers(Checkers):
    def __init__(self, run_on_hardware, player, num_vertical, num_horizontal, num_vertical_pieces, classical_squares, related_squares, q_rel_moves, q_moves, superposition_pieces, status, moves_since_take, king_squares, rules = CheckersRules.QUANTUM_V3, legal_moves = []) -> None:
        self.rules = rules
        self.SIMULATE_QUANTUM = False
        self.player = player
        self.num_vertical = num_vertical
        self.run_on_hardware = run_on_hardware
        self.num_horizontal = num_horizontal
        self.num_vertical_pieces = num_vertical_pieces # how many rows of one color need to be filled with pieces
        self.classical_squares = classical_squares # Contains information about a square (e.g. white, king, etc...)
        self.related_squares = related_squares # List of lists that keep track of squares in superpositions that are related to each other. This way if a square is measured we know the related squares of that square
        self.q_rel_moves = q_rel_moves # parallel to related squares, but keeps track of quantum moves
        self.q_moves = q_moves # Just a list of al quantum moves so we can do them again when doing a new move
        self.white_squares = {}
        self.black_squares = {}
        self.status = status
        self.superposition_pieces = superposition_pieces # contains a list of pieces that started the superposition. This is needed to recreate the board when a move has been done
        self.moves_since_take = moves_since_take # Number of moves since a piece has been taken
        self.king_squares = king_squares
        self.legal_moves = legal_moves
#TODO: Change calculating blind moves to use direction variable for black/white (+1/-1) instead of a very long if else statement
#TODO: Clean up calculating legal moves function with using only 1 for loop
#TODO: Instead of first clearing the entire board and then flipping the pieces, just initialize the pieces immediately correctly
#TODO: 50 percent of time is in the peek function, reduce it?
#TODO: prev_taken, failed = self.classic_move(move) --- Same thing right??
#TODO: check for mcts calculating legal_moves after taking another piece

#TODO: Take another piece after entangling
#TODO: MONTE CARLO:
# INSTEAD OF GETTING ALL POSSIBLE STATES WHEN COLLAPSING, ALREADY TAKE THE POSSIBLE STATES WHEN DOING SUPERPOSITIONS AND ENTANGLEMENT.
# THIS FIXES THE PROBLEM OF NOT KNOWING HOW TO RESOVLE ENTANGLEMENT

 

# if __name__ == '__main__':
    