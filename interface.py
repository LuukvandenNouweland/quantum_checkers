from quantum_checkers import Checkers, Move_id
import pygame
import random
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
# https://quantumchess.net/play/
# https://entanglement-chess.netlify.app/qm
# https://github.com/quantumlib/unitary/blob/main/docs/unitary/getting_started.ipynb

# GLOBAL GUI SETTINGS
# Constants
WIDTH, HEIGHT = 600, 600
SQUARE_W, SQUARE_H = 60, 60
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (51,51,51)
DARK_BROWN = (145,94,42)
LIGHT_BROWN = (231,203,175)
YELLOW = (230,225,7)
L_RED = (221, 0, 0)
RED = (180,2,1)
BLUE = (0, 0, 255)
CROWN_IMG = pygame.image.load(os.path.join(os.path.dirname(__file__), "crown.png"))
CROWN_IMG = pygame.transform.scale(CROWN_IMG, (int(SQUARE_W*0.65), int((CROWN_IMG.get_height()/(CROWN_IMG.get_width()/SQUARE_W))*0.65)))
  
class GameInterface:
    def __init__(self, game: Checkers, GUI = False) -> None:
        self.game = game
        self.quit = False
        self.highlighted_squares = []
        self.status = CheckersResult.UNFINISHED
        self.selected_id = None # Square select by player, used for highlighting and moving pieces
        self.move_locations = set() # If a piece is selected, this variable will store the locations the piece can move to
        open('./log.txt', 'w').close()
        if(GUI == "True"):
            self.GUI = True
            self.init_gui()
        else:
            self.GUI = False       

    def get_move(self):
        return input(f'Player {self.game.player.name} to move: ')
    
    def init_gui(self):
        pygame.init()
        # Initialize the screen
        infoObject = pygame.display.Info()
        width = self.game.num_horizontal*SQUARE_W
        height = self.game.num_vertical*SQUARE_H
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Quantum Checkers")
        # Clock to control the frame rate
        clock = pygame.time.Clock()

    def highlight_squares(self, moves_list: list):
        self.highlighted_squares = []
        self.move_locations.clear()
        movable_pieces = []
        for move in moves_list:
            movable_pieces.append(move.source_id)
            if(move.source_id == self.selected_id):
                self.move_locations.add(move.target1_id)
        if(len(self.move_locations) > 0):
            self.highlighted_squares.append(self.selected_id)
            for i in self.move_locations:
                self.highlighted_squares.append(i)
            return
        # no piece selected that is able to move TODO
        for idx in movable_pieces:
            self.highlighted_squares.append(idx)
        
    def write_to_log(self, move, counter, moves):
        self.log = open("./log.txt", "a")
        self.log.write("#########################\n")
        self.log.write(str(counter))
        st = ": "
        st = move.print_move()
        self.log.write(st)
        self.log.write("\n")
        self.log.write(str(moves))
        self.log.write("\n\n")
        # self.log.write(self.game.get_board())
        self.log.close()

    def play(self):
        counter = 0
        moves = []
        # for i in [9, 3, 7, 3, 5, 3, 9, 3, 9, 1, 4, 9, 6, 5, 2, 6, 1, 8, 1, 1, 2, 2, 4, 1, 1, 1, 4, 4, 4, 8, 3, 1, 3, 1, 11, 15, 5]:
        #     legal_moves = self.get_legal_moves()
        #     self.game.player_move(legal_moves[i-1], self.game.player)
        #     self.print_board()
        while(self.status == CheckersResult.UNFINISHED and not self.quit):
            legal_moves = self.get_legal_moves()
            if(len(legal_moves) == 0):
                self.status = CheckersResult.DRAW
                print("DRAW")
                continue
            if(self.GUI):
                for event in pygame.event.get(): 
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit(0)
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        down_pos = event.pos
                        # self.handle_click(event.pos)
                    if event.type == pygame.MOUSEBUTTONUP:
                        # Detect swipes for quantum moves
                        if(self.handle_click(down_pos, event.pos)):
                            counter += 1
                            print(f"Move number {counter}")
                            legal_moves = self.get_legal_moves() # We have to calculate them again because the player has chanced for the highlight function
                            self.print_board()
                    # self.game.player_move(legal_moves[random.randint(1, len(legal_moves))-1], self.game.player)
                    self.do_game_move(legal_moves[random.randint(1, len(legal_moves))-1])
                    legal_moves = self.get_legal_moves()
                    self.highlight_squares(legal_moves)
                    self.draw_board()
                    pygame.display.flip() # needs to be called outside draw function
                    time.sleep(1)
            else:
                self.print_board()
                self.print_legal_moves(legal_moves) # Changes legal moves to be a list of Move classes for selecting a move
                counter += 1
                print(f"Move number {counter}")
                # move = random.randint(1, len(legal_moves))
                move = self.get_move()
                moves.append(move)
                try:
                    move = int(move)
                except:
                    print("Input has to be an integer!")
                    continue
                if(move > len(legal_moves) or move < 1):
                    print(f"Input has to be an integer between 1 and {len(legal_moves)}!")
                    continue
                print(f"Move is ({move}): ", end="")
                legal_moves[move-1].print_move()
                self.game.player_move(legal_moves[move-1], self.game.player)
                self.write_to_log(legal_moves[move-1], counter, moves)
                # time.sleep(1)

    def draw_circle(self, color, x, y, radius, king = False, highlited = False):
        if(color == RED):
            if(highlited):
                highlight_color = YELLOW
            else:
                highlight_color = RED
            gfxdraw.filled_circle(self.screen, x+SQUARE_W//2, y+SQUARE_H//2, radius, highlight_color)
            gfxdraw.filled_circle(self.screen, x+SQUARE_W//2, y+SQUARE_H//2, radius-int(radius*0.15), L_RED)
            gfxdraw.aacircle(self.screen, x+SQUARE_W//2, y+SQUARE_H//2, radius-int(radius*0.15), L_RED)
            gfxdraw.aacircle(self.screen, x+SQUARE_W//2, y+SQUARE_H//2, radius, highlight_color)
        else:
            if(highlited):
                highlight_color = YELLOW
            else:
                highlight_color = BLACK
            gfxdraw.filled_circle(self.screen, x+SQUARE_W//2, y+SQUARE_H//2, radius, highlight_color)
            gfxdraw.filled_circle(self.screen, x+SQUARE_W//2, y+SQUARE_H//2, radius-int(radius*0.15), GREY)
            gfxdraw.aacircle(self.screen, x+SQUARE_W//2, y+SQUARE_H//2, radius-int(radius*0.15), GREY)
            gfxdraw.aacircle(self.screen, x+SQUARE_W//2, y+SQUARE_H//2, radius, highlight_color)
        if(king):
            c = CROWN_IMG.get_rect(center=(x+SQUARE_W//2, y+SQUARE_H//2)) # centers the image
            self.screen.blit(CROWN_IMG, c)

    def get_positions(self, player) -> [[list, list], [list, list]]:
        """
        Gets the positions of all the pieces from the game.
        Returns two lists of lists of the player positions and opponent positions separated by the normal pieces and king pieces
        """
        return self.game.get_positions(player)

    def draw_board(self):
        self.screen.fill(WHITE)
        white_pieces, black_pieces = self.game.get_advanced_positions(CheckersPlayer.WHITE)
        flip = True
        for id in range(self.game.num_horizontal*self.game.num_vertical):
            # print(f"{id}, {self.game.num_horizontal}, {id % self.game.num_horizontal == 0}")
            if(id % self.game.num_horizontal == 0):
                flip = not flip
            x, y = self.game.convert_id_to_xy(id)
            screen_x = x * SQUARE_W
            screen_y = y * SQUARE_H
            if(flip and self.game.num_horizontal % 2 == 0): # For even length we need to flip the board the squares drawn, not for uneven length
                color = DARK_BROWN if (id) % 2 == 0 else LIGHT_BROWN
            else:
                color = LIGHT_BROWN if (id) % 2 == 0 else DARK_BROWN
            pygame.draw.rect(self.screen, color, (screen_x, screen_y, SQUARE_W, SQUARE_H))
            highlight = True if (id in self.highlighted_squares) else False
            if(str(id) in black_pieces):
                # pygame.draw.circle(self.screen, RED, (screen_x+SQUARE_W//2, screen_y+SQUARE_H//2), int(SQUARE_W-0.15*SQUARE_W)//2)
                self.draw_circle(GREY, screen_x, screen_y, int(SQUARE_W-0.15*SQUARE_W)//2, black_pieces[str(id)].king, highlight)
            elif(str(id) in white_pieces):
                self.draw_circle(RED, screen_x, screen_y, int(SQUARE_W-0.15*SQUARE_W)//2, white_pieces[str(id)].king, highlight)
            elif(id in self.highlighted_squares): # Highlight squares for where the selected piece can move
                gfxdraw.circle(self.screen, screen_x+SQUARE_W//2, screen_y+SQUARE_H//2, int(SQUARE_W-0.15*SQUARE_W)//2, WHITE)
                gfxdraw.aacircle(self.screen, screen_x+SQUARE_W//2, screen_y+SQUARE_H//2, int(SQUARE_W-0.15*SQUARE_W)//2, WHITE)
            
    def get_id_from_mouse_pos(self, x, y):
        x = x // SQUARE_W
        y = y // SQUARE_H
        return self.game.convert_xy_to_id(x, y)

    def do_game_move(self, move: Move_id):
        """
        Do a game move and reset values for GUI
        """
        self.game.player_move(move, self.game.player)
        self.selected_id = -1 # value used in highlight function to check if we need to return
        self.move_locations.clear()
        self.highlighted_squares = []
        return

    def handle_click(self, first_pos, second_pos):
        """
        Handles clicking on the board. Returns true if a move was done
        """
        self.highlighted_squares = []
        mouse_x, mouse_y = first_pos[0], first_pos[1]
        first_id = self.get_id_from_mouse_pos(mouse_x, mouse_y)
        mouse_x, mouse_y = second_pos[0], second_pos[1]
        second_id = self.get_id_from_mouse_pos(mouse_x, mouse_y)
        if(first_id == second_id):
            if(self.selected_id is not None and self.move_locations is not None and first_id in self.move_locations): # We want to move the piece to first id
                self.do_game_move(Move_id(MoveType.CLASSIC, self.game.player, self.selected_id, first_id)) #classic move
                return True
            self.selected_id = first_id
            return False
        elif(self.selected_id is not None and self.move_locations is not None and first_id in self.move_locations and second_id in self.move_locations):
            self.do_game_move(Move_id(MoveType.SPLIT, self.game.player, self.selected_id, first_id, second_id)) #split move
            return True

    def print_board(self) -> str:
        str_board = self.game.get_board()
        print(str_board)
        return str_board
    
    def get_legal_moves(self) -> list:
        moves, _ = self.game.calculate_possible_moves(self.game.player)
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
