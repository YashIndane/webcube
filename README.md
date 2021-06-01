![](https://img.shields.io/badge/-Flask-blue?style=for-the-badge&logo=flask)

# webcube
Rubik's cube assistant on Flask webapp. This webapp accepts the six faces of your cube and gives you the voice instructions as a response.

## Requirements

This webapp requires a lot of extra modules and packages to be downloaded, It is recommanded to follow this order :

```
yum install python3 -y
yum install gcc-c++ -y
yum install python3-devel -y 
pip3 install flask 
pip3 install Pillow
pip3 install numpy
pip3 install joblib
pip3 install scikit-learn
pip3 install scikit-build
pip3 install opencv-python
yum install opencv opencv-devel opencv-python -y
pip3 install kociemba
```

## Usage

This webapp runs on port no. `85` by default, but can be changed in the `app.py` file. To use take edge to edge and centred pics of the cube. 
Start with Red face with the white face down, and take pictures in the order Red -> Green -> Orange -> Blue -> Yellow -> White. After this click `get solution`.

## Working

The six images of six faces have there respective `data_uri`, which are submitted by a form when you click `get solution`. This `data_uri` are converted to images and saved.

## Building docker image

build docker image by ->

`docker build -t <username>/<repo-name>:<version>`

## deploying the image in Kubernetes

create a deployment by ->

`kubectl create deployment <deploy-name> --image <username>/<repo-name>:<version> `

Scale the deployment if necessary and create a service by ->

`kubectl expose <deploy-name> --port=85 --name=<service-name> --type=LoadBalancer`
