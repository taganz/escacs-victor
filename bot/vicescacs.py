import chess
# from stockfish import Stockfish
import chess.svg
import time
import random
# import requests
import json
import os


BOOK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opening_book.json")
with open(BOOK_PATH, encoding="utf-8") as file:
    OPENING_BOOK = json.load(file)


# with open("opening_book.json", encoding="utf-8") as file:
#     OPENING_BOOK = json.load(file)

# stockfish = Stockfish("D:\\MODS\\CHESS\\stockfish\\stockfish-windows-x86-64-avx2.exe")
# stockfish.set_depth(20)
# stockfish.set_skill_level(20)
wait_time = 1
board = chess.Board()



PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0
}


PAWN_TABLE = [
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
    [0.1, 0.1, 0.2, 0.3, 0.3, 0.2, 0.1, 0.1],
    [0.1, 0.1, 0.2, 0.3, 0.3, 0.2, 0.1, 0.1],
    [0.0, 0.0, 0.0, 0.2, 0.2, 0.0, 0.0, 0.0],
    [0.1, -0.1, -0.2, 0.0, 0.0, -0.2, -0.1, 0.1],
    [0.1, 0.2, 0.2, -0.2, -0.2, 0.2, 0.2, 0.1],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
]


KNIGHT_TABLE = [
    [-0.5, -0.4, -0.3, -0.3, -0.3, -0.3, -0.4, -0.5],
    [-0.4, -0.2,  0.0,  0.0,  0.0,  0.0, -0.2, -0.4],
    [-0.3,  0.0,  0.2,  0.3,  0.3,  0.2,  0.0, -0.3],
    [-0.3,  0.1,  0.3,  0.4,  0.4,  0.3,  0.1, -0.3],
    [-0.3,  0.0,  0.3,  0.4,  0.4,  0.3,  0.0, -0.3],
    [-0.3,  0.1,  0.2,  0.3,  0.3,  0.2,  0.1, -0.3],
    [-0.4, -0.2,  0.0,  0.1,  0.1,  0.0, -0.2, -0.4],
    [-0.5, -0.4, -0.3, -0.3, -0.3, -0.3, -0.4, -0.5]
]


BISHOP_TABLE = [
    [-0.2, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.2],
    [-0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.1],
    [-0.1,  0.0,  0.1,  0.2,  0.2,  0.1,  0.0, -0.1],
    [-0.1,  0.1,  0.1,  0.2,  0.2,  0.1,  0.1, -0.1],
    [-0.1,  0.0,  0.2,  0.2,  0.2,  0.2,  0.0, -0.1],
    [-0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.1, -0.1],
    [-0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.1],
    [-0.2, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.2]
]


ROOK_TABLE = [
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.0],
    [-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.1],
    [-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.1],
    [-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.1],
    [-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.1],
    [0.0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.0],
    [0.0, 0.0, 0.0, 0.1, 0.1, 0.0, 0.0, 0.0]
]


QUEEN_TABLE = [
    [-0.2, -0.1, -0.1, 0.0, 0.0, -0.1, -0.1, -0.2],
    [-0.1,  0.0,  0.0, 0.0, 0.0,  0.0,  0.0, -0.1],
    [-0.1,  0.0,  0.1, 0.1, 0.1,  0.1,  0.0, -0.1],
    [ 0.0,  0.0,  0.1, 0.1, 0.1,  0.1,  0.0,  0.0],
    [ 0.0,  0.0,  0.1, 0.1, 0.1,  0.1,  0.0,  0.0],
    [-0.1,  0.0,  0.1, 0.1, 0.1,  0.1,  0.0, -0.1],
    [-0.1,  0.0,  0.0, 0.0, 0.0,  0.0,  0.0, -0.1],
    [-0.2, -0.1, -0.1, 0.0, 0.0, -0.1, -0.1, -0.2]
]


KING_TABLE = [
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.2, -0.3, -0.3, -0.4, -0.4, -0.3, -0.3, -0.2],
    [-0.1, -0.2, -0.2, -0.2, -0.2, -0.2, -0.2, -0.1],
    [ 0.2,  0.2,  0.0,  0.0,  0.0,  0.0,  0.2,  0.2],
    [ 0.2,  0.3,  0.1,  0.0,  0.0,  0.1,  0.3,  0.2]
]


PIECE_TABLES = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE
}


class Bot:
    def __init__(self, name ,move_selection):
        self.pick_move = move_selection
        self.score = 0
        self.color = ""
        self.name = name

    def clear_score(self):
        self.score = 0
        self.color = ""


def minimax_move(board):
    return best_move(board, 4)

def random_move(board):
    return random.choice(list(board.legal_moves))

def oldminimax_move(board):
    return oldbest_move(board, 4)


def color_piece_points(color):
    score = 0
    for piece, value in PIECE_VALUES.items():
        score += value * len(board.pieces(piece, color))
    return score

def piece_points():
    points = color_piece_points(chess.WHITE) + color_piece_points(chess.BLACK)
    return points

def update_fen():
    with open("board.txt", "w") as f:
        f.write(board.fen())

# def update_stockfish():
#     stockfish.set_fen_position(board.fen())

def evaluate(board):
    if board.is_checkmate():
        return -99999 if board.turn else 99999

    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0

    for square, piece in board.piece_map().items():

        # Mirror black's square so the table is always
        # interpreted from White's perspective.
        if piece.color == chess.BLACK:
            square = chess.square_mirror(square)

        rank = chess.square_rank(square)
        file = chess.square_file(square)

        material_value = PIECE_VALUES[piece.piece_type]
        positional_value = PIECE_TABLES[piece.piece_type][rank][file]

        value = material_value + positional_value

        if piece.color == chess.WHITE:
            score += value
        else:
            score -= value

    return score

#OLD CODE
def oldminimax(board, depth):
    if depth == 0 or board.is_game_over():
        return evaluate(board)

    if board.turn == chess.WHITE:
        max_eval = -float("inf")

        for move in board.legal_moves:
            board.push(move)
            evaluation = oldminimax(board, depth - 1)
            board.pop()

            max_eval = max(max_eval, evaluation)

        return max_eval

    else:
        min_eval = float("inf")

        for move in board.legal_moves:
            board.push(move)
            evaluation = oldminimax(board, depth - 1)
            board.pop()

            min_eval = min(min_eval, evaluation)

        return min_eval


def oldbest_move(board, depth):
    best_move_found = None

    if board.turn == chess.WHITE:
        best_value = -float("inf")

        for move in board.legal_moves:
            board.push(move)
            value = oldminimax(board, depth - 1)
            board.pop()

            if value > best_value:
                best_value = value
                best_move_found = move

    else:
        best_value = float("inf")

        for move in board.legal_moves:
            board.push(move)
            value = oldminimax(board, depth - 1)
            board.pop()

            if value < best_value:
                best_value = value
                best_move_found = move

    return best_move_found
#OLD CODE END

def match(board,white, black):
    board.reset()
    move_50_rule = 0 #Aquesta nomès aplica quan nomès queden els reis vius, la original es quan no es fa cap captura.

    while True:
        if move_50_rule == 50:
            break
        else:
            try: board.push(white.pick_move(board))
            except IndexError: break
            try: board.push(black.pick_move(board))
            except IndexError: break
            if piece_points() == 0:
                break
            with open("board.txt", "w") as f:
                f.write(board.fen())

    with open("board.txt", "w") as f:
        f.write(board.fen())

    if board.is_checkmate() and board.turn == False:
        white.score += 1
        print(f"White {white.name} wins, checkmate")

    if board.is_checkmate() and board.turn == True:
        black.score += 1
        print(f"Black {black.name} wins, checkmate")




def tournament(player1, player2, matches):
    for i in range(matches):
        if i % 2 == 0:
            match(board, player1, player2)
        else:
            match(board, player2, player1)




def get_position_key(board):
    # Keep only:
    # piece placement
    # whose turn it is
    # castling rights
    # en passant square
    return " ".join(board.fen().split()[:4])


def get_opening_move(board):

    position = get_position_key(board)

    # Check if the position exists in the opening book
    if position not in OPENING_BOOK:
        return None

    moves = OPENING_BOOK[position]

    move_names = list(moves.keys())
    weights = list(moves.values())

    # Choose a move, weighted by how often it appeared
    selected_move = random.choices(
        move_names,
        weights=weights
    )[0]

    return chess.Move.from_uci(selected_move)


# def get_opening_move(board):
#     url = "https://explorer.lichess.ovh/masters"
#
#     params = {
#         "fen": board.fen(),
#         "moves": 10
#     }
#
#     headers = {
#         "Authorization": f"Bearer {API_TOKEN}"
#     }
#
#     try:
#         response = requests.get(
#             url,
#             params=params,
#             headers=headers,
#             timeout=5
#         )
#
#         response.raise_for_status()
#         data = response.json()
#
#     except requests.exceptions.RequestException as e:
#         print("Lichess request failed:", e)
#         return None
#
#     except ValueError:
#         print("Lichess returned invalid JSON")
#         return None
#
#     moves = data.get("moves", [])
#
#     if not moves:
#         return None
#
#     return chess.Move.from_uci(moves[0]["uci"])
#




def minimax(board, depth, alpha, beta):

    # Base case
    if depth == 0 or board.is_game_over():
        return evaluate(board)

    # White's turn → maximize
    if board.turn == chess.WHITE:

        max_eval = -float("inf")

        for move in board.legal_moves:

            board.push(move)

            evaluation = minimax(
                board,
                depth - 1,
                alpha,
                beta
            )

            board.pop()

            max_eval = max(max_eval, evaluation)

            # Update alpha
            alpha = max(alpha, evaluation)

            # Alpha-beta pruning
            if beta <= alpha:
                break

        return max_eval

    # Black's turn → minimize
    else:

        min_eval = float("inf")

        for move in board.legal_moves:

            board.push(move)

            evaluation = minimax(
                board,
                depth - 1,
                alpha,
                beta
            )

            board.pop()

            min_eval = min(min_eval, evaluation)

            # Update beta
            beta = min(beta, evaluation)

            # Alpha-beta pruning
            if beta <= alpha:
                break

        return min_eval
# def minimax(board, depth, is_maximizing):
#     if depth == 0 or board.is_game_over():
#         return evaluate(board)
#
#     if is_maximizing:
#         max_eval = -float("inf")
#         for move in board.legal_moves:
#             board.push(move)
#             eval = minimax(board, depth - 1, False)
#             board.pop()
#             max_eval = max(max_eval, eval)
#         return max_eval
#
#     else:
#         min_eval = float("inf")
#         for move in board.legal_moves:
#             board.push(move)
#             eval = minimax(board, depth - 1, True)
#             board.pop()
#             min_eval = min(min_eval, eval)
#         return min_eval


def best_move(board, depth):

    # Check the opening book first
    opening_move = get_opening_move(board)

    if opening_move is not None:
        return opening_move

    # If we're out of the opening book, use Minimax
    first_new_move = True
    if first_new_move:
        print("Out of theory")
        first_new_move = False

    best_move_found = None

    alpha = -float("inf")
    beta = float("inf")

    # White tries to maximize the evaluation
    if board.turn == chess.WHITE:

        best_value = -float("inf")

        for move in board.legal_moves:

            board.push(move)

            value = minimax(
                board,
                depth - 1,
                alpha,
                beta
            )

            board.pop()

            if value > best_value:
                best_value = value
                best_move_found = move

            alpha = max(alpha, best_value)

    # Black tries to minimize the evaluation
    else:

        best_value = float("inf")

        for move in board.legal_moves:

            board.push(move)

            value = minimax(
                board,
                depth - 1,
                alpha,
                beta
            )

            board.pop()

            if value < best_value:
                best_value = value
                best_move_found = move

            beta = min(beta, best_value)

    return best_move_found


# def best_move(board, depth):
#
#     best_move_found = None
#
#     alpha = -float("inf")
#     beta = float("inf")
#
#     # White's turn → maximize
#     if board.turn == chess.WHITE:
#
#         best_value = -float("inf")
#
#         for move in board.legal_moves:
#
#             board.push(move)
#
#             value = minimax(
#                 board,
#                 depth - 1,
#                 alpha,
#                 beta
#             )
#
#             board.pop()
#
#             if value > best_value:
#
#                 best_value = value
#                 best_move_found = move
#
#             alpha = max(alpha, best_value)
#
#     # Black's turn → minimize
#     else:
#
#         best_value = float("inf")
#
#         for move in board.legal_moves:
#
#             board.push(move)
#
#             value = minimax(
#                 board,
#                 depth - 1,
#                 alpha,
#                 beta
#             )
#
#             board.pop()
#
#             if value < best_value:
#
#                 best_value = value
#                 best_move_found = move
#
#             beta = min(beta, best_value)
#
#     return best_move_found

# def best_move(board, depth):
#     best_move = None
#     best_value = -float("inf")
#
#     for move in board.legal_moves:
#         board.push(move)
#         value = minimax(board, depth - 1, False)
#         board.pop()
#
#         if value > best_value:
#             best_value = value
#             best_move = move
#
#     return best_move



def choose_move(board: chess.Board, time_limit) -> chess.Move:
    move = best_move(board, 4)
    return move

#TEST
if __name__ == "__main__":
    # while not board.is_game_over():
    #
    #     # Player turn
    #     while True:
    #         try:
    #             board.push_san(input("Enter your move: "))
    #             update_fen()
    #             #update_stockfish()
    #             break
    #         except ValueError:
    #             print("Invalid move")
    #
    #     print(color_piece_points(chess.WHITE))
    #
    #
    #
    #
    #
    #     # Computer turn
    #     try:
    #         #board.push(random.choice(list(board.legal_moves)))
    #         #board.push_san(stockfish.get_top_moves(1)[0].get("Move"))
    #         board.push(best_move(board, 4))
    #         time.sleep(random.uniform(1, 2))
    #         update_fen()
    #         #update_stockfish()
    #     except IndexError:
    #         break
    #
    #     print(color_piece_points(chess.BLACK))
    #
    # if board.is_checkmate():
    #     if board.turn == chess.WHITE:
    #         print("Black wins! Checkmate!")
    #     elif board.turn == chess.BLACK:
    #         print("White wins! Checkmate!")
    # elif board.is_stalemate():
    #     print("Draw!")
    #
    #
    #
    #
    #
    #
    #
    #
    # bot1 = Bot("newminimax",minimax_move)
    # bot2 = Bot("oldminimax",random_move)
    #
    # bot1.clear_score()
    # bot2.clear_score()
    # # tournament(bot1, bot2, matches=100)
    # print(bot1.score, bot1.name)
    # print(bot2.score, bot2.name)
    #
    # board.reset()
    # update_fen()

    pass
