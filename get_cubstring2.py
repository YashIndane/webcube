from openai import OpenAI
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import base64
import json
import sys
import io

client = OpenAI(api_key="<OPENAI-API-KEY>")

# ──────────────────────────────────────────────
# 1. IMAGE PREPROCESSING (lighter touch for good lighting)
# ──────────────────────────────────────────────

def preprocess_image(image_path: str) -> bytes:
    """Light preprocessing — just enough to improve edge clarity."""
    img = Image.open(image_path).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.2)       # subtle contrast boost
    img = ImageEnhance.Sharpness(img).enhance(1.5)      # sharpen tile borders
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=2))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=97)
    return buf.getvalue()


def to_b64(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def crop_tile(image_path: str, row: int, col: int, grid_size: int = 3) -> bytes:
    """Crop a single tile with padding, then upscale it."""
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    tile_w, tile_h = w // grid_size, h // grid_size
    pad = 8

    left   = max(0, col * tile_w + pad)
    top    = max(0, row * tile_h + pad)
    right  = min(w, (col + 1) * tile_w - pad)
    bottom = min(h, (row + 1) * tile_h - pad)

    tile = img.crop((left, top, right, bottom))
    tile = tile.resize((300, 300), Image.LANCZOS)
    buf = io.BytesIO()
    tile.save(buf, format="JPEG", quality=97)
    return buf.getvalue()


# ──────────────────────────────────────────────
# 2. PROMPTS
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# 3. API CALLS
# ──────────────────────────────────────────────

def call_gpt4o_single(image_bytes: bytes, prompt: str, max_tokens: int = 150) -> str:
    b64 = to_b64(image_bytes)
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
    """Send both original and preprocessed images in same API call."""
    b64_orig = to_b64(original_bytes)
    b64_proc = to_b64(processed_bytes)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text",      "text": "Image 1 — Original photo:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_orig}", "detail": "high"}},
                {"type": "text",      "text": "Image 2 — Sharpened version:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_proc}", "detail": "high"}},
                {"type": "text",      "text": prompt}
            ]
        }],
        max_tokens=max_tokens,
        temperature=0  # deterministic output
    )
    return response.choices[0].message.content


def parse_json(text: str) -> dict:
    clean = text.strip()
    if "```" in clean:
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    return json.loads(clean.strip())


# ──────────────────────────────────────────────
# 4. MAIN PIPELINE
# ──────────────────────────────────────────────

POSITION_ORDER = [
    "top-left", "top-center", "top-right",
    "mid-left", "mid-center", "mid-right",
    "bot-left", "bot-center", "bot-right"
]

def analyze_rubiks_face(image_path: str) -> list[list[dict]]:
    original_bytes  = Path(image_path).read_bytes()
    processed_bytes = preprocess_image(image_path)

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
            tile_bytes  = crop_tile(image_path, row, col)
            tile_raw    = call_gpt4o_single(tile_bytes, SINGLE_TILE_PROMPT)
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


# ──────────────────────────────────────────────
# 5. DISPLAY
# ──────────────────────────────────────────────

def print_grid(grid: list):
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
    from collections import Counter
    counts = Counter(flat)
    print(f"\n📊 Color counts: { dict(counts) }")

    return flat


def generate_cubestring():
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
