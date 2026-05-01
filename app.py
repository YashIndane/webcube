import logging
import cubestring_openai
import cubestring_gemini
import argparse

from flask import Flask, render_template, request
from base64 import b64decode
from PIL import Image
from io import BytesIO
from subprocess import getstatusoutput as gso
from solve_cube import get_moves

app = Flask("webcube")


@app.route("/input")
def input():
    return render_template("input.html")


@app.route("/process", methods=["POST"])
def get_instructions():
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

    moves = get_moves(cubestring)
  
    gso("echo 'y' | cp static/k8s.js static/out.js")

    for v in moves :
        v = '"' + v + '"' 
        gso(f"echo '  speak({v});' >> static/out.js")
        gso("echo '  await sleep(3500);' >> static/out.js")
    gso("echo '})()' >> static/out.js")

    return render_template("output.html")


class NoGetFilter:
    def filter(self, record):
        return  "POST" not in record.getMessage()


if __name__ == "__main__":
    
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
