import logging

from flask import Flask, render_template, request
from base64 import b64decode
from PIL import Image
from io import BytesIO
from subprocess import getstatusoutput as gso
from get_cubstring2 import generate_cubestring
#from get_cubestring_gemini_rl import generate_cubestring 
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

  #openai
  #cubestring = generate_cubestring()
  #moves = get_moves(cubestring)

  #gemini
  cubestring = generate_cubestring()
  moves = get_moves(cubestring)

  
  #order()
  #generated_cubestring = get_cubestring()
  #moves = get_moves(generated_cubestring)
  
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

#Configure logger
log = logging.getLogger('werkzeug')
log.addFilter(NoGetFilter())

app.run(host="0.0.0.0", port=85)
