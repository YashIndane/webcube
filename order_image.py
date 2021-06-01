import cv2
import joblib
import numpy as np

def order() :

  order = ["yellow", "green", "red", "white", "blue", "orange"]
  colours = ["orange", "red", "green", "blue", "yellow", "white"]

  s_scalar = joblib.load("Scalar1")
  model = joblib.load("model_0.04")

  counter = 0

  for color in order :
    for n in range(6) :
      image = cv2.imread(f"face{n}.png")
      rgb_array = []
      for x in image[193][200] :
        rgb_array.append(x)
      n_array = np.array([rgb_array])
      arr = s_scalar.transform([rgb_array])
      value = model.predict(arr)
      index = value[0] - 1
      if colours[index] == color :
        cv2.imwrite(f"face_{counter}.png", image)
        counter += 1
        break
