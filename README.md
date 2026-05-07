![](https://img.shields.io/badge/-Flask-blue?style=for-the-badge&logo=flask) ![](https://img.shields.io/badge/impressions-79.7k-lightblue?style=for-the-badge&logo=linkedin) ![](https://img.shields.io/badge/likes-2.7k-lightblue?style=for-the-badge&logo=linkedin)

# webcube
Rubik's cube assistant on Flask webapp. This webapp accepts the six faces of your cube and gives you the voice instructions as a response.

Demo -> [Link](https://www.linkedin.com/posts/yash-indane-aa6534179_machinelearning-flask-python-activity-6805902901546901507-dN6M)

## Usage

Navigate to `http://<IP>:<PORT>/input`.
This webapp runs on port no. `85` by default, but can be changed in the `app.py` file. To use take edge to edge and centred pics of the cube. 
Start with `Red` face with the `White` face down, and take pictures in the order `Yellow -> Green -> Red -> White -> Blue -> Orange`. After this click `get solution`. While listening to the instructions face the `Red` centred face with the `White` centred face down.

![example](https://user-images.githubusercontent.com/53041219/207019696-abfe8bbe-4ce9-48fb-bd4a-268b4ab9b7c7.png)

## Running the container

```
sudo docker run -dit -p 5000:85 --name <container-name> <image:version> --apikey="<OPENAI/GEMINI API-KEY>" --mod="<openai/gemini>"
```

## Working

The six images of six faces have there respective `data_uri`, which are submitted by a form when you click `get solution`. This `data_uri` are converted to images and saved. Each image of the face of cube is processed by LLM, due to get the 9 tile colors. This tile colors build up the cubestring, which is then processed by the kociemba library to get the optimal solution to the cube.

## Cube String notation

<img width="919" height="708" alt="image" src="https://github.com/user-attachments/assets/7df62b44-fc7f-4569-ba37-094678642611" />

```py
colour_mappings = {
    "red": "F",
    "green": "R",
    "blue": "L",
    "yellow": "U",
    "white": "D",
    "orange": "B"
 }
```

The cubestring is passed to the `kociemba.solve()` function, which return a string containing instructions for solving the cube.
Kociemba is a Python/C implementation of Herbert Kociemba's Two-Phase algorithm for solving Rubik's Cube.

Read full documentation of Kociemba here -> [Link](https://pypi.org/project/kociemba/)

the instructions are decoded to human voice instructions. This instructions are then written to the `output.js` file, which outputs this instructions as voice.

## Building docker image

build docker image by ->

`$ docker build -t <username>/<repo-name>:<version>`

I have also uploded already build image for this webapp on Docker Hub -> [Link](https://hub.docker.com/repository/docker/yashindane/webcube)

## deploying the image in Kubernetes

create a deployment by ->

`$ kubectl create deployment <deploy-name> --image <username>/<repo-name>:<version> `

Scale the deployment if necessary and create a service by ->

`$ kubectl expose deployment <deploy-name> --port=85 --name=<service-name> --type=LoadBalancer`

## Prerequisite browser settings

### 1. Remove chrome managed by your organisation (Optional)

Visit this link -> [link](https://www.youtube.com/watch?v=DaLaWChdyug)

### 2. Edit chrome flags for camera access

Navigate to `chrome://flags/#unsafely-treat-insecure-origin-as-secure` on chrome browser and add `http://<IP>:<PORT>` inside `Insecure origins treated as secure box` and click enable and reload the chrome page.
After usage just remove the entry and click disable.
