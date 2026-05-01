import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageFilter
from collections import Counter, deque
import json
import sys
import time

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────

genai.configure(api_key="")
MODEL = "gemini-2.5-flash"


# ──────────────────────────────────────────────
# RATE LIMITER — gemini-2.5-flash allows 5 RPM
# ──────────────────────────────────────────────

class RateLimiter:
    """Sliding window rate limiter — ensures max N calls per 60 seconds."""
    def __init__(self, max_calls: int = 5, period: int = 60):
        self.max_calls = max_calls
        self.period    = period
        self.calls     = deque()  # timestamps of recent calls

    def wait(self):
        now = time.time()

        # Remove timestamps older than the window
        while self.calls and now - self.calls[0] >= self.period:
            self.calls.popleft()

        if len(self.calls) >= self.max_calls:
            # Must wait until the oldest call falls outside the window
            wait_time = self.period - (now - self.calls[0]) + 1
            print(f"  ⏳ Rate limit reached ({self.max_calls} RPM) — waiting {wait_time:.1f}s...")
            time.sleep(wait_time)
            # Clean up again after sleeping
            now = time.time()
            while self.calls and now - self.calls[0] >= self.period:
                self.calls.popleft()

        self.calls.append(time.time())

rate_limiter = RateLimiter(max_calls=5, period=60)


# ──────────────────────────────────────────────
# 1. IMAGE PREPROCESSING
# ──────────────────────────────────────────────

def preprocess_image(image_path: str) -> Image.Image:
    """Light preprocessing — sharpen edges, subtle contrast boost."""
    img = Image.open(image_path).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=2))
    return img


def crop_tile(image_path: str, row: int, col: int) -> Image.Image:
    """Crop and upscale a single tile for close-up re-analysis."""
    img = Image.open(image_path).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(1.5)

    w, h = img.size
    tile_w, tile_h = w // 3, h // 3
    pad = 8

    left   = max(0, col * tile_w + pad)
    top    = max(0, row * tile_h + pad)
    right  = min(w, (col + 1) * tile_w - pad)
    bottom = min(h, (row + 1) * tile_h - pad)

    tile = img.crop((left, top, right, bottom))
    tile = tile.resize((300, 300), Image.LANCZOS)
    return tile


# ──────────────────────────────────────────────
# 2. JSON SCHEMAS
# Note: Gemini SDK does NOT support minItems/maxItems — removed
# ──────────────────────────────────────────────

COLORS     = ["white", "yellow", "red", "orange", "blue", "green"]
CONFIDENCE = ["high", "medium", "low"]

TILE_SCHEMA = {
    "type": "object",
    "properties": {
        "color_groups": {"type": "string"},
        "tile_analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pos":        {"type": "string"},
                    "color":      {"type": "string", "enum": COLORS},
                    "confidence": {"type": "string", "enum": CONFIDENCE}
                },
                "required": ["pos", "color", "confidence"]
            }
        }
    },
    "required": ["color_groups", "tile_analysis"]
}

SINGLE_TILE_SCHEMA = {
    "type": "object",
    "properties": {
        "color":      {"type": "string", "enum": COLORS},
        "confidence": {"type": "string", "enum": CONFIDENCE}
    },
    "required": ["color", "confidence"]
}

VALIDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "valid":  {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {"type": "string"}
        },
        "suggested_grid": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "string", "enum": COLORS}
            }
        }
    },
    "required": ["valid", "issues", "suggested_grid"]
}


# ──────────────────────────────────────────────
# 3. PROMPTS
# ──────────────────────────────────────────────

RUBIKS_PROMPT = """
You are an expert Rubik's cube color detector. You will receive TWO versions of the same cube face:
- Image 1: the original photo
- Image 2: a lightly sharpened version to help distinguish tile boundaries

Identify the color of all 9 tiles in the 3x3 grid.

━━━ COLOR RULES ━━━
WHITE  → very low saturation, bright. NOT yellow.
YELLOW → warm, golden. NOT white or orange.
RED    → dark, deep. NOT bright or warm.
ORANGE → bright, vivid, warm. NOT dark like red.
BLUE   → cool hue, medium-dark. NOT green.
GREEN  → clearly green. NOT teal or blue.

Red vs Orange: Red is DARKER. Orange is BRIGHTER.
White vs Yellow: White has NO color. Yellow is warm/golden.

Return tile_analysis for all 9 positions in this exact order:
top-left, top-center, top-right,
mid-left, mid-center, mid-right,
bot-left, bot-center, bot-right

Only use: white, yellow, red, orange, blue, green
Confidence: high, medium, or low
"""

SINGLE_TILE_PROMPT = """
This is a close-up of ONE Rubik's cube tile. Good lighting.

WHITE=bright no color, YELLOW=warm golden, RED=dark deep,
ORANGE=bright vivid warm, BLUE=cool medium-dark, GREEN=clearly green

Identify the color and your confidence level.
Only use: white, yellow, red, orange, blue, green
"""

VALIDATION_PROMPT = """
You are validating a Rubik's cube face color reading.

Current grid reading:
{grid_json}

Rules for a valid Rubik's cube face:
- Exactly 9 tiles total
- The CENTER tile is always a single solid color — it is the face's true color
- A single face can realistically have at most 5-6 different colors

Check if any colors seem wrong given the center tile color is: {center_color}
If the reading looks valid, return it unchanged in suggested_grid.
If something seems off, correct it in suggested_grid.
Always return all 3 rows of 3 colors in suggested_grid.
"""


# ──────────────────────────────────────────────
# 4. GEMINI API CALLS
# ──────────────────────────────────────────────

def call_gemini(parts: list, schema: dict, max_tokens: int = 2048) -> dict:
    """
    Call Gemini with forced JSON schema output.
    Handles empty/null responses gracefully.
    Rate limited to 5 RPM for gemini-2.5-flash.
    """
    rate_limiter.wait()  # enforce rate limit before every API call
    model = genai.GenerativeModel(
        MODEL,
        generation_config=genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0,
            response_mime_type="application/json",
            response_schema=schema
        )
    )
    response = model.generate_content(parts)

    # Guard: empty or whitespace response
    raw = response.text.strip() if response.text else ""
    if not raw or raw in ("null", "None", ""):
        print(f"  ⚠️  Gemini returned empty response — using fallback.")
        return {}

    # Guard: response is just "null" JSON value
    try:
        parsed = json.loads(raw)
        if parsed is None:
            return {}
        return parsed
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON decode failed: {e}")
        print(f"  Raw response: {raw[:200]}")
        return {}


def call_gemini_validation(img: Image.Image, prompt: str) -> dict:
    """
    Send validation request.
    Falls back to 'valid' if Gemini returns empty/bad response.
    """
    result = call_gemini([img, prompt], VALIDATION_SCHEMA, max_tokens=400)

    # If response was empty or malformed, treat as valid — skip corrections
    if not result:
        print("  ⚠️  Validation response empty — skipping corrections, assuming valid.")
        return {"valid": True, "issues": [], "suggested_grid": []}

    return result


def call_gemini_dual(original_img: Image.Image, processed_img: Image.Image, prompt: str) -> dict:
    """Send both original and preprocessed images in one Gemini call."""
    parts = [
        "Image 1 — Original photo:",
        original_img,
        "Image 2 — Sharpened version:",
        processed_img,
        prompt
    ]
    return call_gemini(parts, TILE_SCHEMA, max_tokens=2048)


def call_gemini_single_tile(img: Image.Image, prompt: str) -> dict:
    """Send a single tile image for close-up analysis."""
    return call_gemini([img, prompt], SINGLE_TILE_SCHEMA, max_tokens=100)


# ──────────────────────────────────────────────
# 5. MAIN PIPELINE
# ──────────────────────────────────────────────

POSITION_ORDER = [
    "top-left", "top-center", "top-right",
    "mid-left", "mid-center", "mid-right",
    "bot-left", "bot-center", "bot-right"
]


def analyze_rubiks_face(image_path: str) -> list[list[dict]]:
    """
    Full 3-pass pipeline:
    Pass 1 — Dual-image full face analysis
    Pass 2 — Re-check low/medium confidence tiles individually
    Pass 3 — Logical validation using center tile as ground truth
    """
    original_img  = Image.open(image_path).convert("RGB")
    processed_img = preprocess_image(image_path)

    # ── Pass 1: Dual-image full face analysis ──
    print("🔍 Pass 1: Full face analysis (dual image)...")
    result    = call_gemini_dual(original_img, processed_img, RUBIKS_PROMPT)
    raw_tiles = result.get("tile_analysis", [])

    # Safely map tiles — pad with fallback if Gemini returns fewer than 9
    tiles = {}
    for i, pos in enumerate(POSITION_ORDER):
        if i < len(raw_tiles):
            entry = raw_tiles[i]
            entry["pos"] = pos  # ensure pos is always correct
            tiles[pos]   = entry
        else:
            tiles[pos] = {"pos": pos, "color": "white", "confidence": "low"}

    print(f"🎨 Colors seen: {result.get('color_groups', 'N/A')}\n")
    print("Pass 1 readings:")
    for pos in POSITION_ORDER:
        t    = tiles[pos]
        icon = "✅" if t["confidence"] == "high" else "⚠️ " if t["confidence"] == "medium" else "❌"
        print(f"  {icon} {pos:<14} → {t['color']}")

    # ── Pass 2: Re-check uncertain tiles individually ──
    uncertain = [
        (i, pos) for i, pos in enumerate(POSITION_ORDER)
        if tiles[pos]["confidence"] in ("low", "medium")
    ]

    if uncertain:
        print(f"\n🔁 Pass 2: Re-checking {len(uncertain)} uncertain tile(s)...")
        for idx, pos in uncertain:
            row, col    = divmod(idx, 3)
            tile_img    = crop_tile(image_path, row, col)
            tile_result = call_gemini_single_tile(tile_img, SINGLE_TILE_PROMPT)

            original  = tiles[pos]["color"]
            corrected = tile_result["color"]

            if original != corrected:
                print(f"  🔄 {pos}: {original} → {corrected}")
                tiles[pos]["color"]      = corrected
                tiles[pos]["confidence"] = tile_result["confidence"]
            else:
                print(f"  ✔  {pos}: confirmed {original}")
    else:
        print("\n✅ All tiles high confidence — skipping Pass 2.")

    # ── Pass 3: Logical validation ──
    print("\n🧩 Pass 3: Logical validation...")
    center_color = tiles["mid-center"]["color"]
    grid_colors  = [
        [tiles[POSITION_ORDER[r * 3 + c]]["color"] for c in range(3)]
        for r in range(3)
    ]

    validation_prompt = VALIDATION_PROMPT.format(
        grid_json=json.dumps(grid_colors),
        center_color=center_color
    )
    val_result = call_gemini_validation(original_img, validation_prompt)

    if not val_result.get("valid") and val_result.get("issues"):
        print(f"  ⚠️  Issues found: {val_result['issues']}")
        suggested = val_result.get("suggested_grid", [])
        if len(suggested) == 3 and all(len(row) == 3 for row in suggested):
            for r in range(3):
                for c in range(3):
                    pos = POSITION_ORDER[r * 3 + c]
                    tiles[pos]["color"] = suggested[r][c]
            print("  🔄 Applied suggested corrections.")
        else:
            print("  ⚠️  Suggested grid malformed — skipping corrections.")
    else:
        print("  ✅ Grid looks valid.")

    return [[tiles[POSITION_ORDER[r * 3 + c]] for c in range(3)] for r in range(3)]


# ──────────────────────────────────────────────
# 6. DISPLAY
# ──────────────────────────────────────────────

def print_grid(grid: list) -> list:

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

    counts = Counter(flat)
    print(f"\n📊 Color counts: {dict(counts)}")
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
