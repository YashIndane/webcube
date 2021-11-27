from flask import Flask, render_template, request
from base64 import b64decode
from PIL import Image
from io import BytesIO
from order_image import order
from cubestring import get_cubestring
from moves import get_moves
from subprocess import getstatusoutput as gso

app = Flask("webcube")

@app.route("/input")
def input():
  return render_template("input.html")

@app.route("/process", methods=["GET"])
def get_instructions():

  for i in range(6):
    uri_string = request.args.get(f"ur{i}")
    uri_string = uri_string[uri_string.index(",") + 1:]
    im = Image.open(BytesIO(b64decode(uri_string)))
    im.save(f"face{i}.png", "PNG")

  order()
  generated_cubestring = get_cubestring()
  moves = get_moves(generated_cubestring)
  
  gso("echo 'y' | cp static/k8s.js static/out.js")

  for v in moves :
    v = '"' + v + '"' 
    gso(f"echo '  speak({v});' >> static/out.js")
    gso("echo '  await sleep(3500);' >> static/out.js")
  gso("echo '})()' >> static/out.js")

  return render_template("output.html")

app.run(host="0.0.0.0", port=1185)