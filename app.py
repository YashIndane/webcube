#!/usr/bin/python3

# Main application file for webcube

import logging
import argparse

from PIL import Image
from io import BytesIO
from typing import List
from base64 import b64decode
from flask import Flask, render_template, request
from src.utilities.webcube_utilities import get_moves, build_output_js_file
from src.workflows import cubestring_gemini, cubestring_openai


app = Flask("webcube")


@app.route("/input")
def input():
    return render_template("input.html")


@app.route("/process", methods=["POST"])
def get_instructions():
    """Endpoint to kick the whole workflow"""
    for i in range(6):
        uri_string = request.form.get(f"ur{i}")
        uri_string = uri_string[uri_string.index(",") + 1:]
        im = Image.open(BytesIO(b64decode(uri_string)))
        im.save(f"face{i}.png", "PNG")

    #generate the cubestring
    if PLATFORM == 'openai':
        cubestring = cubestring_openai.generate_cubestring(api_key=API_KEY)
    elif PLATFORM == 'gemini':
        cubestring = cubestring_gemini.generate_cubestring(api_key=API_KEY)

    #moves from kociemba
    moves: List = get_moves(cubestring)

    #add instructions to out.js file
    build_output_js_file(moves)

    return render_template("output.html")

class NoGetFilter:
    def filter(self, record):
        return  "POST" not in record.getMessage()


def main():

    global API_KEY, PLATFORM

    #Parse Args
    parser = argparse.ArgumentParser()
    parser.add_argument(
            "--mod", help="OpenAI or Gemini, for cubestring generation", required=True)
    parser.add_argument(
            "--apikey", help="OpenAI or Gemini API key", required=True)
    args = parser.parse_args()

    API_KEY, PLATFORM = args.apikey, args.mod
    
    #Configure logger
    log = logging.getLogger('werkzeug')
    log.addFilter(NoGetFilter())

    app.run(host="0.0.0.0", port=85)

if __name__ == "__main__":
    main()
