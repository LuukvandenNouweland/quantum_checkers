from quantum_checkers import Checkers, Move_id
from players import human_player

import numpy as np
import pygame
import random
from time import sleep
from enums import (
    CheckersResult,
    CheckersPlayer,
    MoveType
)
import os
from pygame import gfxdraw
import time
# GUI
import pygame
import sys
from copy import deepcopy
# https://quantumchess.net/play/
# https://entanglement-chess.netlify.app/qm
# https://github.com/quantumlib/unitary/blob/main/docs/unitary/getting_started.ipynb

# GLOBAL GUI SETTINGS
# Constants

class GameInterface:
    def __init__(self, game: Checkers, white_player, black_player) -> None:
        self.game = game
        self.quit = False
        self.highlighted_squares = []
        self.selected_id = None # Square select by player, used for highlighting and moving pieces
        self.move_locations = set() # If a piece is selected, this variable will store the locations the piece can move to
        self.draw_chance = False
        self.white_player = white_player
        self.black_player = black_player
    
    def play(self):
        counter = 0
        moves = []
        prev_take = False # variable to check if a piece has been taken before
        # for i in [3, 2, 2, 1, 1, 2, 2, 1]:
        #     # legal_moves = self.get_legal_moves()
        #     self.game.player_move(self.game.legal_moves[i-1], self.game.player)
        #     self.print_board(False)
        while(self.game.status == CheckersResult.UNFINISHED and not self.quit):
            self.print_board(False)
            self.print_legal_moves(self.game.legal_moves)
            if(self.game.player == CheckersPlayer.WHITE):
                move = self.white_player.select_move(self.game.legal_moves)
            else:
                move = self.black_player.select_move(self.game.legal_moves)
            moves.append(move)
            print("Selected move: ", end="")
            move.print_move()
            self.game.player_move(move, self.game.player)
            # if(len(self.game.legal_moves) > 0):
            #     prev_take = True
            # self.write_to_log(move, counter, moves)
            # time.sleep(1)
        # self.print_board()
        print(f"Result: {self.game.status}")
        return(self.game.status, counter)

    def get_positions(self, player) -> [[list, list], [list, list]]:
        """
        Gets the positions of all the pieces from the game.
        Returns two lists of lists of the player positions and opponent positions separated by the normal pieces and king pieces
        """
        return self.game.get_positions(player)

    def print_board(self, simulated: bool) -> str:
        # str_board = self.game.get_sim_board()
        if(not simulated):
            str_board = self.game.get_board()
        else:
            str_board = self.game.get_sim_board()
        print(str_board)
        return str_board
    
    def get_legal_moves(self) -> list:
        moves = self.game.calculate_possible_moves(self.game.player)
        return moves

    def print_legal_moves(self, legal_moves = None) -> list:
        """
        Prints all legal moves the current player can do
        """
        index = 1 # Start counter at 1
        if(legal_moves == None):
            legal_moves = self.get_legal_moves()
        for move in legal_moves:
            move.print_move(index=index)
            index += 1
        # print(legal_moves)
        # for key, value in legal_moves.items():
        #     if(type(value) == list and len(value) > 1):
        #         print(f"{str(index)}: [{key}] to [{value[0]}]")
        #         legal_moves_list.append(Move_id(source_id=key, target1_id=value[0]))
        #         index += 1
        #         print(f"{str(index)}: [{key}] to [{value[1]}]")
        #         legal_moves_list.append(Move_id(source_id=key, target1_id=value[1]))
        #         index+=1
        #         print(f"{str(index)}: [{key}] to [{value[0]}] and [{value[1]}]")
        #         legal_moves_list.append(Move_id(source_id=key, target1_id=value[0], target2_id=value[1]))
        #     else:
        #         print(f"{str(index)}: [{key}] to [{value[0]}]")
        #         legal_moves_list.append(Move_id(source_id=key, target1_id=value[0]))
        #     index +=1
        return legal_moves
