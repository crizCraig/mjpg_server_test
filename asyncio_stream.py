import asyncio
import os
import threading
import time
import traceback
from collections import deque

import cv2
from aiohttp import web
import aiohttp_jinja2
import jinja2
import subprocess


stream_queue = deque(maxlen=10)


async def uptime_handler(request):
    # http://HOST:PORT/?interval=90
    interval = 1

    # Without the Content-Type, most (all?) browsers will not render
    # partially downloaded content. Note, the response type is
    # StreamResponse not Response.
    resp = web.StreamResponse(status=200,
                              reason='OK',
                              headers={'Content-Type': 'text/html'})

    # The StreamResponse is a FSM. Enter it with a call to prepare.
    await resp.prepare(request)

    while True:
        try:
            # Technically, subprocess blocks, so this is a dumb call
            # to put in an async example. But, it's a tiny block and
            # still mocks instantaneous for this example.
            await resp.write(b"<strong>")
            await resp.write(subprocess.check_output('uptime'))
            await resp.write(b"</strong><br>\n")

            # Yield to the scheduler so other processes do stuff.
            await resp.drain()

            # This also yields to the scheduler, but your server
            # probably won't do something like this.
            await asyncio.sleep(interval)
        except Exception as e:
            # So you can observe on disconnects and such.
            print(repr(e))
            raise

    return resp


@aiohttp_jinja2.template('index.html')
async def home_handler(request):
    return {}


class VideoCamera(object):
    def __init__(self):
        # Using OpenCV to capture from device 0. If you have trouble capturing
        # from a webcam, comment the line below out and use a video file
        # instead.
        # self.video = cv2.VideoCapture(0)
        # If you decide to use video.mp4, you must have this file in the fo\lder
        # as the main.py.
        self.video = cv2.VideoCapture('marmatt.mp4')

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        # We are using Motion JPEG, but OpenCV defaults to capture raw images,
        # so we must encode it into JPEG in order to correctly display the
        # video stream.
        try:
            ret, jpeg = cv2.imencode('.jpg', image)
        except Exception as e:
            print('Exception encoding image ' + str(e))
            return None
        return jpeg.tobytes()


async def mjpg_stream_handler(request):
    # http://HOST:PORT/?interval=90
    camera = VideoCamera()

    # Without the Content-Type, most (all?) browsers will not render
    # partially downloaded content. Note, the response type is
    # StreamResponse not Response.
    resp = web.StreamResponse(status=200,
                              reason='OK',
                              headers={'Content-Type': 'multipart/x-mixed-replace; boundary=frame'})

    # The StreamResponse is a finite state machine. Enter it with a call to prepare.
    await resp.prepare(request)

    while True:
        frame = None
        try:
            if len(stream_queue) > 0 and frame is not stream_queue[-1]:
                frame = stream_queue[-1]

                await resp.write(b'--frame\r\n'
                                 b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

            # Yield to the scheduler so other processes do stuff.
            await resp.drain()

            # # This also yields to the scheduler, but your server
            # # probably won't do something like this.
            # await asyncio.sleep(0.010)
        except Exception as e:
            # So you can observe on disconnects and such.
            print(repr(e))
            # raise
            traceback.print_tb(e.__traceback__)
            raise

    return resp


async def build_server(loop, address, port):
    # For most applications -- those with one event loop --
    # you don't need to pass around a loop object. At anytime,
    # you can retrieve it with a call to asyncio.get_event_loop().
    # Internally, aiohttp uses this pattern a lot. But, sometimes
    # "explicit is better than implicit." (At other times, it's
    # noise.)
    app = web.Application(loop=loop)
    template_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
    aiohttp_jinja2.setup(app,
                         loader=jinja2.FileSystemLoader(template_dir))
    app.router.add_route('GET', "/uptime", uptime_handler)
    app.router.add_route('GET', "/mjpg-stream", mjpg_stream_handler)
    app.router.add_route('GET', "/", home_handler)

    return await loop.create_server(app.make_handler(), address, port)


def frame_worker():
    camera = VideoCamera()

    while True:
        frame = camera.get_frame()

        if frame is None:
            camera = VideoCamera()
            frame = camera.get_frame()

        stream_queue.append(frame)
        time.sleep(1/60)


def main():

    frame_thread = threading.Thread(target=frame_worker)
    frame_thread.start()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(build_server(loop, 'localhost', 5000))
    print("Server ready at http://localhost:5000")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Shutting Down!")
        loop.close()


if __name__ == '__main__':
    main()
