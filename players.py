from random import randint

class bot():
    def __init__(self) -> None:
        pass

    def select_move(self, possible_moves):
        pass

class human_player(bot):
    def select_move(self, possible_moves):
        selected = False
        while not selected:
            move = self.get_move()
            try:
                move = int(move)
            except:
                print("Input has to be an integer!")
            if(move > len(possible_moves) or move < 1):
                print(f"Input has to be an integer between 1 and {len(possible_moves)}!")
                continue
            selected = True
        return possible_moves[move-1]
    
    def get_move(self):
        return input(f'Select move: ')

class random_bot(bot):
    def select_move(self, possible_moves):
        return possible_moves[randint(0, len(possible_moves)-1)]
            
