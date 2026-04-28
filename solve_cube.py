import kociemba
from typing import List

KOCIEMBA_MAPPINGS = {
                    'blue': 'L',
                    'red': 'F',
                    'yellow': 'U',
                    'green': 'R',
                    'orange': 'B',
                    'white': 'D',
                    }

def build_cubestring(cols: List) -> str:
    cubestring = ''
    for color in cols:
        cubestring += KOCIEMBA_MAPPINGS[color['color'].lower()]
    return cubestring
