# Process the face of a Cube"""

import io
import base64

from PIL import Image, ImageEnhance, ImageFilter

class FaceImage:
    """Class to process the Face image of the cube, before
    feeding it to LLM"""

    def __init__(self, *, image_path: str | None) -> None:
        self.image_path = image_path

    def preprocess_image_openai(self) -> bytes:
        """Light preprocessing — just enough to improve edge clarity.

           Opens the image from the instance path and applies a sequence of
           enhancements: a subtle contrast boost, mild sharpening, and an unsharp
           mask filter to accentuate tile borders. The final image is serialized
           to a JPEG byte buffer at near-lossless quality for API consumption.

           Returns:
               bytes: The preprocessed image encoded as a high-quality JPEG
                   (quality=97) in a raw bytes format, suitable for direct
                   transmission to the OpenAI API.
        """

        img = Image.open(self.image_path).convert("RGB")
        # subtle contrast boost
        img = ImageEnhance.Contrast(img).enhance(1.2)

        # sharpen tile borders
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=2))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=97)

        return buf.getvalue()

    def preprocess_image_gemini(self) -> Image.Image:
        """Light preprocessing — sharpen edges, subtle contrast boost.

           Opens the image from the instance path and applies a sequence of
           enhancements: a subtle contrast boost, mild sharpening, and an
           unsharp mask filter to accentuate edges for improved clarity.

           Returns:
               Image.Image: A preprocessed PIL Image in RGB mode with enhanced
                   contrast, sharpness, and edge definition via an unsharp mask
                   (radius=1, percent=120, threshold=2).
        """

        img = Image.open(self.image_path).convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=2))
        return img


    def crop_tile_openai(self, row: int, col: int, grid_size: int = 3) -> bytes:
        """Crops a specific tile from an image grid, shrinks it by an inner margin, 
        and resizes it to JPEG bytes.

        This method splits the image stored at `self.image_path` into a square grid 
        defined by `grid_size`. It extracts the tile at the specified row and column, 
        trims an 8-pixel internal border from all sides, upscales/downscales the 
        result to a fixed 300x300 resolution using Lanczos resampling, and compresses 
        it into a high-quality JPEG byte stream.

        Args:
            row (int): The 0-indexed row position of the target tile in the grid.
            col (int): The 0-indexed column position of the target tile in the grid.
            grid_size (int, optional): The number of rows and columns to split the 
            image into. Defaults to 3 (creating a 3x3 grid).

        Returns:
            bytes: The raw byte array representing the final 300x300 JPEG image.
         """

        img = Image.open(self.image_path).convert("RGB")
        w, h = img.size
        tile_w, tile_h = w // grid_size, h // grid_size
        pad = 8

        left = max(0, col * tile_w + pad)
        top = max(0, row * tile_h + pad)
        right = min(w, (col + 1) * tile_w - pad)
        bottom = min(h, (row + 1) * tile_h - pad)

        tile = img.crop((left, top, right, bottom))
        tile = tile.resize((300, 300), Image.LANCZOS)
        buf = io.BytesIO()
        tile.save(buf, format="JPEG", quality=97)

        return buf.getvalue()
    

    def crop_tile_gemini(self, row: int, col: int) -> Image.Image:
        """Crop and upscale a single tile for close-up re-analysis.

           Opens the image from the instance path, applies contrast and sharpness
           enhancements, then crops a specific tile from a 3x3 grid layout with
           inward padding. The cropped tile is resized to 300x300 pixels using
           LANCZOS resampling for high-quality upscaling.

           Args:
               row (int): The row index of the tile in the 3x3 grid (0-based).
               col (int): The column index of the tile in the 3x3 grid (0-based).

           Returns:
               Image.Image: A 300x300 PIL Image of the specified tile, enhanced
                   and upscaled using LANCZOS resampling.
        """

        img = Image.open(self.image_path).convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = ImageEnhance.Sharpness(img).enhance(1.5)

        w, h = img.size
        tile_w, tile_h = w // 3, h // 3
        pad = 8

        left = max(0, col * tile_w + pad)
        top  = max(0, row * tile_h + pad)
        right = min(w, (col + 1) * tile_w - pad)
        bottom = min(h, (row + 1) * tile_h - pad)

        tile = img.crop((left, top, right, bottom))
        tile = tile.resize((300, 300), Image.LANCZOS)

        return tile
    
    @staticmethod
    def to_b64(image_bytes: bytes) -> str:
        """Convert image bytes to base64 encoded string.

           Args:
               image_bytes (bytes): The raw image bytes to be encoded.

           Returns:
               str: A base64 encoded string representation of the image bytes,
                    decoded as UTF-8.
        """

        return base64.standard_b64encode(image_bytes).decode("utf-8")
