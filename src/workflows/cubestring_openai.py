import json

from openai import OpenAI
from pathlib import Path
from typing import List, Dict
from src.image_processing.face import FaceImage
from src.utilities.webcube_utilities import (
    parse_json,
    print_grid,
)


#Prompts
RUBIKS_PROMPT = """
You are an expert Rubik's cube color detector. You will receive TWO versions of the same cube face:
- Image 1: the original photo
- Image 2: a lightly sharpened version to help distinguish tile boundaries

Your task is to identify the color of all 9 tiles in the 3x3 grid.

━━━ COLOR IDENTIFICATION RULES ━━━
For EACH tile, first describe what you physically see (hue, brightness, saturation), then map it:

WHITE  → very low saturation, bright. May look slightly cream or grey. NOT yellow.
YELLOW → warm, medium-high brightness, clearly yellow/golden. NOT white or orange.
RED    → dark, deep, low brightness. Think blood red or brick red. NOT bright/warm.
ORANGE → bright, warm, clearly between red and yellow. More vivid than red. NOT dark.
BLUE   → cool hue, medium-dark. Could be royal blue or navy. NOT green or purple.
GREEN  → clearly green hue. Could be forest or lime green. NOT teal or blue.

━━━ COMMON MISTAKES TO AVOID ━━━
- Red vs Orange: Red is DARKER and less saturated. Orange is BRIGHTER and more vivid.
- White vs Yellow: White has almost NO color. Yellow is clearly warm/golden.
- Blue vs Green: Blue is cool/cold hue. Green has a warm-ish or neutral hue.

━━━ PROCESS ━━━
Step 1) Look at all 9 tiles. List how many distinct colors you see and roughly where.
Step 2) For each tile position, describe its hue and brightness in one phrase.
Step 3) Assign the final color name.

Return ONLY this JSON (no extra text, no markdown):
{
  "color_groups": "brief description of distinct colors seen across the face",
  "tile_analysis": [
    {"pos": "top-left",     "observation": "dark deep red, low brightness", "color": "red",    "confidence": "high"},
    {"pos": "top-center",   "observation": "...", "color": "...", "confidence": "..."},
    {"pos": "top-right",    "observation": "...", "color": "...", "confidence": "..."},
    {"pos": "mid-left",     "observation": "...", "color": "...", "confidence": "..."},
    {"pos": "mid-center",   "observation": "...", "color": "...", "confidence": "..."},
    {"pos": "mid-right",    "observation": "...", "color": "...", "confidence": "..."},
    {"pos": "bot-left",     "observation": "...", "color": "...", "confidence": "..."},
    {"pos": "bot-center",   "observation": "...", "color": "...", "confidence": "..."},
    {"pos": "bot-right",    "observation": "...", "color": "...", "confidence": "..."}
  ]
}

Only use these 6 colors: white, yellow, red, orange, blue, green
Confidence must be: high, medium, or low
"""

SINGLE_TILE_PROMPT = """
This is a close-up of ONE tile from a Rubik's cube. The lighting is good.

Describe exactly what color you see (hue, brightness, saturation), then pick the closest match.

━━━ RULES ━━━
WHITE  → almost no color, very bright/neutral
YELLOW → warm, golden, clearly not white
RED    → dark, deep red — darker than orange
ORANGE → bright vivid warm color, clearly not dark like red
BLUE   → cool hue, medium to dark
GREEN  → clearly green, not blue or teal

Return ONLY this JSON:
{"observation": "describe exactly what you see", "color": "red", "confidence": "high"}
"""

VALIDATION_PROMPT = """
You are validating a Rubik's cube face color reading.

Current grid reading:
{grid_json}

Rules for a valid Rubik's cube face:
- Exactly 9 tiles total
- The CENTER tile is always a single solid color — it is the face's "true" color
- A single face can realistically have at most 5-6 different colors
- No color should appear more than 9 times (that would mean all tiles are same color)

Check if any colors seem wrong given the center tile color is: {center_color}
If the reading looks valid, return it unchanged.
If something seems off, flag which tiles might be wrong.

Return ONLY this JSON:
{{
  "valid": true,
  "issues": [],
  "suggested_grid": <same format as input grid>
}}
"""

def call_gpt4o_single(image_bytes: bytes, prompt: str, max_tokens: int = 150) -> str:
    """Send a single image and prompt to GPT-4o for analysis.

    Encodes the provided image bytes to a base64 JPEG data URL and submits
    it alongside the given text prompt to the GPT-4o model via the OpenAI
    chat completions API. The request uses high-detail image processing and
    a temperature of 0 for deterministic output.

    Args:
        image_bytes (bytes): Raw image bytes to be encoded and sent to
            the model as a high-detail JPEG data URL.
        prompt (str): The text instruction or question to accompany the
            image in the user message.
        max_tokens (int, optional): Maximum number of tokens in the
            model's response. Defaults to 150.

    Returns:
        str: The text content of the first choice returned by GPT-4o.

    Raises:
        openai.OpenAIError: If the API request fails or returns an
            unexpected response.
    """

    b64 = FaceImage.to_b64(image_bytes)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
                {"type": "text", "text": prompt}
            ]
        }],
        max_tokens=max_tokens,
        temperature=0  # deterministic output
    )
    return response.choices[0].message.content


def call_gpt4o_dual(original_bytes: bytes, processed_bytes: bytes, prompt: str, max_tokens: int = 800) -> str:
    """Send both original and preprocessed images in same API call.

    Encodes both the original and preprocessed image bytes as base64 JPEG
    data URLs and submits them together in a single GPT-4o chat completion
    request. The images are labelled as 'Image 1 - Original photo' and
    'Image 2 - Sharpened version' respectively, followed by the text prompt.
    Both images are sent at high detail and temperature is set to 0 for
    deterministic output.

    Args:
        original_bytes (bytes): Raw bytes of the original, unprocessed image.
        processed_bytes (bytes): Raw bytes of the preprocessed (sharpened)
            image to be compared against the original.
        prompt (str): The text instruction or question to accompany both
            images in the user message.
        max_tokens (int, optional): Maximum number of tokens in the model's
            response. Defaults to 800.

    Returns:
        str: The text content of the first choice returned by GPT-4o.

    Raises:
        openai.OpenAIError: If the API request fails or returns an
            unexpected response.
    """

    b64_orig = FaceImage.to_b64(original_bytes)
    b64_proc = FaceImage.to_b64(processed_bytes)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Image 1 — Original photo:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_orig}", "detail": "high"}},
                {"type": "text", "text": "Image 2 — Sharpened version:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_proc}", "detail": "high"}},
                {"type": "text", "text": prompt}
            ]
        }],
        max_tokens=max_tokens,
        temperature=0  # deterministic output
    )
    return response.choices[0].message.content

POSITION_ORDER = [
    "top-left", "top-center", "top-right",
    "mid-left", "mid-center", "mid-right",
    "bot-left", "bot-center", "bot-right"
]

def analyze_rubiks_face(image_path: str) -> List[List[Dict]]:
    """Analyze a single Rubik's Cube face image using a three-pass GPT-4o pipeline.

    Executes a three-pass analysis strategy to accurately identify the color
    of each tile in a 3x3 Rubik's Cube face:

    - **Pass 1**: Sends both the original and preprocessed images together to
      GPT-4o for a full-face dual-image analysis, extracting color and
      confidence for all 9 tiles.
    - **Pass 2**: Re-examines any tiles with low or medium confidence by
      cropping and sending each uncertain tile individually to GPT-4o for
      a closer single-tile analysis. Corrections are applied where the
      re-check disagrees with Pass 1.
    - **Pass 3**: Performs a logical validation of the full 3x3 grid using
      the center tile as the face's reference color. If issues are detected,
      GPT-4o's suggested corrections are applied to the final grid.

    Args:
        image_path (str): Path to the face image file (e.g. 'face0.png')
            to be analyzed.

    Returns:
        List[List[Dict]]: A 3x3 nested list of tile dictionaries, where
            each dict contains at minimum:
            - 'color' (str): The identified color of the tile.
            - 'confidence' (str): Confidence level ('high', 'medium', 'low').
            - 'observation' (str): A brief description supporting the color
              classification.

    Side Effects:
        Prints detailed per-pass progress, tile readings, confidence icons,
        any corrections applied, and validation results to stdout.
    """

    original_bytes  = Path(image_path).read_bytes()
    face_image = FaceImage(image_path=image_path)
    processed_bytes = face_image.preprocess_image_openai()

    # ── Pass 1: Dual-image full face analysis ──
    print("🔍 Pass 1: Full face analysis (dual image)...")
    raw    = call_gpt4o_dual(original_bytes, processed_bytes, RUBIKS_PROMPT)
    result = parse_json(raw)

    tiles = {t["pos"]: t for t in result["tile_analysis"]}
    print(f"🎨 Colors seen: {result.get('color_groups', 'N/A')}\n")

    # Print Pass 1 readings
    print("Pass 1 readings:")
    for pos in POSITION_ORDER:
        t = tiles[pos]
        icon = "✅" if t["confidence"] == "high" else "⚠️ " if t["confidence"] == "medium" else "❌"
        print(f"  {icon} {pos:<14} → {t['color']:<7}  ({t['observation']})")

    # ── Pass 2: Re-check uncertain tiles individually ──
    uncertain = [(i, pos) for i, pos in enumerate(POSITION_ORDER)
                 if tiles[pos]["confidence"] in ("low", "medium")]

    if uncertain:
        print(f"\n🔁 Pass 2: Re-checking {len(uncertain)} uncertain tile(s)...")
        for idx, pos in uncertain:
            row, col = divmod(idx, 3)
            tile_bytes = face_image.crop_tile_openai(row, col)
            tile_raw = call_gpt4o_single(tile_bytes, SINGLE_TILE_PROMPT)
            tile_result = parse_json(tile_raw)

            original  = tiles[pos]["color"]
            corrected = tile_result["color"]

            if original != corrected:
                print(f"  🔄 {pos}: {original} → {corrected}  | {tile_result['observation']}")
                tiles[pos]["color"]      = corrected
                tiles[pos]["confidence"] = tile_result["confidence"]
            else:
                print(f"  ✔  {pos}: confirmed {original}")
    else:
        print("\n✅ All tiles high confidence — skipping Pass 2.")

    # ── Pass 3: Logical validation ──
    print("\n🧩 Pass 3: Logical validation...")
    grid_for_validation = [[tiles[POSITION_ORDER[r * 3 + c]] for c in range(3)] for r in range(3)]
    center_color = tiles["mid-center"]["color"]

    validation_prompt = VALIDATION_PROMPT.format(
        grid_json=json.dumps([[t["color"] for t in row] for row in grid_for_validation]),
        center_color=center_color
    )
    val_raw    = call_gpt4o_single(original_bytes, validation_prompt, max_tokens=300)
    val_result = parse_json(val_raw)

    if not val_result.get("valid") and val_result.get("issues"):
        print(f"  ⚠️  Issues found: {val_result['issues']}")
        # Apply suggested corrections
        suggested = val_result.get("suggested_grid")
        if suggested:
            for r in range(3):
                for c in range(3):
                    pos = POSITION_ORDER[r * 3 + c]
                    tiles[pos]["color"] = suggested[r][c]
            print("  🔄 Applied suggested corrections.")
    else:
        print("  ✅ Grid looks valid.")

    # Build final 3x3 grid
    return [[tiles[POSITION_ORDER[r * 3 + c]] for c in range(3)] for r in range(3)]


def generate_cubestring(*, api_key: str):
    """Analyze all six Rubik's Cube faces and generate a kociemba cube string.

    Initializes a global OpenAI client with the provided API key, then
    iterates over all six face images (face0.png through face5.png),
    analyzing each with the Rubik's face analyzer to extract a 3x3 color
    grid. The flat color lists from all faces are concatenated and mapped
    to their corresponding kociemba notation characters to produce the
    final 54-character cube state string.

    Kociemba face mappings:
        blue -> L, red -> F, yellow -> U,
        green -> R, orange -> B, white -> D

    Args:
        api_key (str): The OpenAI API key used to initialize the global
            client for vision-based face analysis. Must be passed as a
            keyword argument.

    Returns:
        str: A 54-character kociemba cube state string representing the
            colors of all six faces in order, suitable for input to a
            kociemba solver.

    Side Effects:
        Sets the global `client` variable to a new OpenAI instance.
        Prints analysis progress and the final cube string to stdout.
    """

    global client
    client = OpenAI(api_key=api_key)

    KOCIEMBA_MAPPINGS = {
                        'blue': 'L',
                        'red': 'F',
                        'yellow': 'U',
                        'green': 'R',
                        'orange': 'B',
                        'white': 'D',
                        }
    COL_LIST = []
    for i in range(6):
        IMAGE_PATH = f"face{i}.png"
        print(f"\n🎲 Analyzing Rubik's face: {IMAGE_PATH}")
        print("=" * 45)
        grid = analyze_rubiks_face(IMAGE_PATH)
        #appending the flat color list of a face
        COL_LIST.extend(print_grid(grid))
    
    cubestring = "".join(
        KOCIEMBA_MAPPINGS[color.lower()]
        for color in COL_LIST
    )
    
    print(f"CUBESTRING: {cubestring}")
    return cubestring
