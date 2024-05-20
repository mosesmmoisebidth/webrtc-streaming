# Import necessary modules
from aiortc import RTCPeerConnection, RTCSessionDescription
import cv2
from fastapi.responses import FileResponse, StreamingResponse
import json
import jsonify
import uuid
import asyncio
from uvicorn import Config, Server
import logging
from fastapi.middleware.cors import CORSMiddleware
import time
from fastapi import FastAPI, Request
import socketio

from starlette.staticfiles import StaticFiles


# Create a Flask app instance
app = FastAPI()
app.mount('/static', StaticFiles(directory="static"), name="static")
sio = socketio.AsyncServer(
    async_mode='asgi',
    logger=True,
    cors_allowed_origins=[],
    engineio_logger=True
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
sio_app = socketio.ASGIApp(
    socketio_server=sio,
    socketio_path='/socket.io'
)
# Set to keep track of RTCPeerConnection instances
pcs = set()

@sio.event
async def connect(sid, environ, auth):
    print("CONNECTED WITH SID: {}".format(sid))

@sio.event
async def disconnect(sid):
    print("DISCONNECTED WITH SID: {}".format(sid))

# Function to generate video frames from the camera
def generate_frames():
    camera = cv2.VideoCapture(0)
    while True:
        start_time = time.time()
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            # Concatenate frame and yield for streaming
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            elapsed_time = time.time() - start_time
            logging.debug(f"Frame generation time: {elapsed_time} seconds")


# Route to render the HTML template
@app.get('/')
def index():
    return FileResponse('static/index.html', media_type="text/html")
async def offer_async(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    pc = RTCPeerConnection()
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

def offer(request: Request):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(offer_async(request))



# Route to handle the offer request
@app.post('/offer')
async def offer_route(request: Request):
    return await offer(request)



# Route to stream video frames
@app.get('/video_feed')
def video_feed():
    return StreamingResponse(generate_frames(), media_type='multipart/x-mixed-replace; boundary=frame')

@app.on_event("startup")
async def handle_startup():
    print("SERVER STARTED RUNNING")

@app.on_event("shutdown")
async def handle_shutdown():
    print("SERVER STOPPED RUNNING")
# Run the Flask app
if __name__ == "__main__":
    config = Config(app, host='127.0.0.1', port=8002, reload=True)
    server = Server(config=config)
    server.run()
