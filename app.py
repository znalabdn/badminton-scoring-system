from flask import Flask, render_template, request, jsonify
import sqlite3
import time
import csv
import os
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

# Global variables
players = {
    "player1": {"name": "Player 1", "score": 0, "sets": 0, "points_won": 0},
    "player2": {"name": "Player 2", "score": 0, "sets": 0, "points_won": 0}
}
history = []  # Store the results of each set
match_results = []  # Store results after each match
max_sets = 3  # Best of 3 matches
match_winner = None
last_action = None  # Track the last point scored
undone_action = None  # Track the last undone action
start_time = None  # Timer start time
timer_running = False  # Flag to track if timer is running


def connect_db():
    """Connect to SQLite database."""
    return sqlite3.connect('badminton.db')


@app.route('/')
def index():
    return render_template(
        'index.html',
        players=players,
        history=history,
        match_results=match_results,
        match_winner=match_winner
    )


@app.route('/update_name', methods=['POST'])
def update_name():
    """Update the name of a player."""
    data = request.json
    player_key = data.get("player")
    new_name = data.get("name")

    if player_key in players and new_name:
        players[player_key]["name"] = new_name
        return jsonify({"success": True, "name": new_name}), 200

    return jsonify({"success": False, "error": "Invalid data"}), 400


@app.route('/player1_point', methods=['POST'])
def player1_point():
    global last_action, undone_action
    players["player1"]["score"] += 1
    players["player1"]["points_won"] += 1
    last_action = {"player": "player1", "score": 1}  # Store last action
    undone_action = None  # Clear undone action after new action
    update_score()
    return jsonify(players)


@app.route('/player2_point', methods=['POST'])
def player2_point():
    global last_action, undone_action
    players["player2"]["score"] += 1
    players["player2"]["points_won"] += 1
    last_action = {"player": "player2", "score": 1}  # Store last action
    undone_action = None  # Clear undone action after new action
    update_score()
    return jsonify(players)


@app.route('/undo_last_point', methods=['POST'])
def undo_last_point():
    """Undo the last point scored."""
    global last_action, undone_action
    if last_action:
        player = last_action["player"]
        if players[player]["score"] > 0:
            players[player]["score"] -= last_action["score"]
            players[player]["points_won"] -= last_action["score"]
            undone_action = last_action  # Save undone action
            last_action = None  # Clear last action since it's undone
    return jsonify(players)


@app.route('/redo_last_point', methods=['POST'])
def redo_last_point():
    """Redo the last undone point."""
    global undone_action
    if undone_action:
        player = undone_action["player"]
        players[player]["score"] += undone_action["score"]
        players[player]["points_won"] += undone_action["score"]
        undone_action = None  # Clear the undone action after redoing
    return jsonify(players)


@app.route('/reset_match', methods=['POST'])
def reset_match():
    global match_winner
    players["player1"]["score"] = 0
    players["player2"]["score"] = 0
    players["player1"]["sets"] = 0
    players["player2"]["sets"] = 0
    players["player1"]["points_won"] = 0
    players["player2"]["points_won"] = 0
    history.clear()
    match_results.clear()
    match_winner = None
    return jsonify(players)


@app.route('/start_timer', methods=['POST'])
def start_timer():
    """Start or stop the match timer."""
    global start_time, timer_running
    if not timer_running:
        start_time = time.time()
        timer_running = True
    else:
        start_time = None
        timer_running = False
    return jsonify({"start_time": start_time, "timer_running": timer_running})


@app.route('/get_timer', methods=['GET'])
def get_timer():
    """Calculate elapsed time for the match."""
    if start_time:
        elapsed_time = int(time.time() - start_time)
    else:
        elapsed_time = 0
    return jsonify({"elapsed_time": elapsed_time})


def update_score():
    """Update the score and check if a player wins a set or the match."""
    global match_winner

    if players["player1"]["score"] >= 21 and players["player1"]["score"] - players["player2"]["score"] >= 2:
        players["player1"]["sets"] += 1
        save_set_result(players["player1"]["name"], players["player1"]["score"], players["player2"]["score"])
        reset_set()
        check_match_winner()

    elif players["player2"]["score"] >= 21 and players["player2"]["score"] - players["player1"]["score"] >= 2:
        players["player2"]["sets"] += 1
        save_set_result(players["player2"]["name"], players["player2"]["score"], players["player1"]["score"])
        reset_set()
        check_match_winner()


def reset_set():
    """Reset scores for the next set."""
    players["player1"]["score"] = 0
    players["player2"]["score"] = 0


def save_set_result(winner_name, player1_score, player2_score):
    """Save the result of the current set and store in the database."""
    history.append(f"Set {len(history) + 1}: {winner_name} won with score {player1_score} - {player2_score}")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO set_history (match_id, set_number, player1_score, player2_score, winner)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (None, len(history), player1_score, player2_score, winner_name)
    )
    conn.commit()
    conn.close()


def check_match_winner():
    """Check if a player has won the match."""
    global match_winner

    if players["player1"]["sets"] > max_sets // 2:
        match_winner = players["player1"]["name"]
        save_match_result(players["player1"]["name"], players["player1"]["sets"], players["player2"]["sets"])
        reset_match_state()

    elif players["player2"]["sets"] > max_sets // 2:
        match_winner = players["player2"]["name"]
        save_match_result(players["player2"]["name"], players["player2"]["sets"], players["player1"]["sets"])
        reset_match_state()


def save_match_result(winner, player1_sets, player2_sets):
    """Save the match result."""
    match_results.append(f"Match: {winner} wins {player1_sets} - {player2_sets}")


def reset_match_state():
    """Reset the match to allow a new match to start while preserving results."""
    players["player1"]["sets"] = 0
    players["player2"]["sets"] = 0
    history.clear()


@app.route('/export_history', methods=['POST'])
def export_history():
    """Export match history to CSV."""
    filename = 'match_history.csv'
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['Set Number', 'Player 1 Score', 'Player 2 Score', 'Winner']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for entry in history:
            # You would break the entry into components here
            writer.writerow({
                'Set Number': entry['set_number'],
                'Player 1 Score': entry['player1_score'],
                'Player 2 Score': entry['player2_score'],
                'Winner': entry['winner']
            })

    return jsonify({'message': 'Match history exported successfully.'})


if __name__ == "__main__":
    app.run(debug=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Default to port 5000 for local development
    app.run(host="0.0.0.0", port=port)
