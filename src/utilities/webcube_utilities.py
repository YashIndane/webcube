# Webcube utility functions

from subprocess import getstatusoutput as gso
from collections import Counter
from typing import List, Dict

import json
import kociemba


def parse_json(text: str) -> Dict:
    """Parse string data to JSON.

    Strips whitespace from the input string and removes any markdown code
    block fences (` ``` `) if present, including the optional 'json' language
    identifier. The cleaned string is then parsed into a dictionary.

    Args:
        text (str): A JSON string, optionally wrapped in markdown code
            block fences (e.g. ```json ... ```).

    Returns:
        Dict: A dictionary parsed from the cleaned JSON string.

    Raises:
        json.JSONDecodeError: If the cleaned string is not valid JSON.
    """

    clean = text.strip()
    if "```" in clean:
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    return json.loads(clean.strip())

def print_grid(grid: List) -> List:
    """Print the grid with color's that have been identfied by the
    LLM, in a nice grid format

    Args:
        grid (List): A grid containing the colors of the solve.
    
    Return:
        List: A list of the detected colors from LLM
    """

    COLOR_CODES = {
        "white":  "\033[97m",
        "yellow": "\033[93m",
        "red":    "\033[91m",
        "orange": "\033[38;5;208m",
        "blue":   "\033[94m",
        "green":  "\033[92m",
    }
    CONF_ICONS = {"high": "✅", "medium": "⚠️ ", "low": "❌"}
    RESET = "\033[0m"
    BOLD  = "\033[1m"

    print(f"\n{BOLD}━━━ Final Rubik's Face Grid ━━━{RESET}")
    print("+" + "─────────────────+" * 3)
    for row in grid:
        color_row = "|"
        conf_row  = "|"
        for tile in row:
            color = tile["color"]
            conf  = tile["confidence"]
            code  = COLOR_CODES.get(color, "")
            color_row += f"{code}{BOLD}  {color:<8}{RESET}       |"
            conf_row  += f"  {CONF_ICONS.get(conf, '  ')} {conf:<8}  |"
        print(color_row)
        print(conf_row)
        print("+" + "─────────────────+" * 3)

    flat = [tile["color"] for row in grid for tile in row]
    print(f"\n📋 Flat (top-left → bottom-right):")
    print(flat)

    # Color count summary
    counts = Counter(flat)
    print(f"\n📊 Color counts: { dict(counts) }")

    return flat

def get_moves(cs: str) -> List:
    """Get the moves from kociemba library, for the scramble.

    Solves the given Rubik's Cube scramble string using the kociemba
    two-phase algorithm and maps each resulting move token to its
    corresponding human-readable rotation instruction.

    Args:
        cs (str): A cube state string in kociemba format representing
            the current scramble to be solved.

    Returns:
        List[str]: An ordered list of human-readable move instructions
            (e.g. 'Rotate left face clockwise') corresponding to the
            solution sequence produced by the kociemba solver. Supports
            all 18 standard Rubik's Cube moves — clockwise (L, R, U, D,
            F, B), anticlockwise (L', R', U', D', F', B'), and
            double turns (L2, R2, U2, D2, F2, B2).

    Raises:
        KeyError: If the solver returns a move token not present in the
            speaking_cmds mapping.
    """

    #Solve the cube
    moves = kociemba.solve(cs)

    speaking_cmds = {
                    'L'   : 'Rotate left face clockwise',
                    'R'   : 'Rotate right face clockwise',
                    'U'   : 'Rotate top face clockwise',
                    'D'   : 'Rotate bottom face clockwise',
                    'F'   : 'Rotate front face clockwise',
                    'B'   : 'Rotate back face clockwise',
                    'L\'' : 'Rotate left face anticlockwise',
                    'R\'' : 'Rotate right face anticlockwise',
                    'U\'' : 'Rotate top face anticlockwise',
                    'D\'' : 'Rotate bottom face anticlockwise',
                    'F\'' : 'Rotate front face anticlokwise',
                    'B\'' : 'Rotate back face anticlockwise',
                    'L2'  : 'Rotate left face twice',
                    'R2'  : 'Rotate right face twice',
                    'U2'  : 'Rotate top face twice',
                    'D2'  : 'Rotate bottom face twice',
                    'F2'  : 'Rotate front face twice',
                    'B2'  : 'Rotate back face twice',
                    }

    return list(
        map(lambda move: speaking_cmds[move], moves.split())
    )

def build_output_js_file(moves: List) -> None:
    """Add instructions to out.js file.

    Iterates over the list of move instructions and appends a
    speak() call followed by a 3500ms sleep delay for each move
    to the static/out.js file. A closing IIFE bracket is appended
    at the end to finalize the JavaScript output file.

    Args:
        moves (List[str]): An ordered list of human-readable move
            instructions to be converted into speak() calls and
            written sequentially to static/out.js.

    Returns:
        None

    Side Effects:
        Appends JavaScript statements to static/out.js, including
        one speak() call and one await sleep(3500) per move, followed
        by a closing '})()' to complete the async IIFE structure.
    """

    #Copy the template JS file
    gso("echo 'y' | cp static/out_template.js static/out.js")

    #Populate the file with the moves
    for move in moves :
            move = '"' + move + '"' 
            gso(f"echo '  speak({move});' >> static/out.js")
            gso("echo '  await sleep(3500);' >> static/out.js")
    gso("echo '})()' >> static/out.js")
