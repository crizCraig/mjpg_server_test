import threading
import time
from collections import deque

import cv2
from flask import Flask, render_template
from werkzeug.wrappers import Response

app = Flask(__name__)


stream_queue = deque(maxlen=10)


class VideoCamera(object):
    def __init__(self):
        # Using OpenCV to capture from device 0. If you have trouble capturing
        # from a webcam, comment the line below out and use a video file
        # instead.
        # self.video = cv2.VideoCapture(0)
        # If you decide to use video.mp4, you must have this file in the folder
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


@app.route('/')
def index():
    return render_template('index.html')


def gen():
    while True:
        frame = None
        if len(stream_queue) > 0 and frame is not stream_queue[-1]:
            frame = stream_queue[-1]
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        else:
            time.sleep(0.01)


@app.route('/mjpg-stream')
def video_feed():
    return Response(gen(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


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

    server = 'CherryPy'

    if server == 'Twisted':

        input('This will cause a giant memory leak, continue?')

        from twisted.internet import reactor
        from twisted.web.server import Site
        from twisted.web.wsgi import WSGIResource

        resource = WSGIResource(reactor, reactor.getThreadPool(), app)
        site = Site(resource)

        reactor.listenTCP(5000, site)
        reactor.run()
    elif server == 'CherryPy':
        import cherrypy
        from paste.translogger import TransLogger
        max_concurrent_streams = 10

        # Enable WSGI access logging via Paste
        app_logged = TransLogger(app)

        # Mount the WSGI callable object (app) on the root directory
        cherrypy.tree.graft(app_logged, '/')

        # Set the configuration of the web server
        cherrypy.config.update({
            'engine.autoreload.on': False,
            'checker.on': False,
            'tools.log_headers.on': False,
            'request.show_tracebacks': False,
            'request.show_mismatched_params': False,
            'log.screen': False,
            'server.socket_port': 5000,
            'server.socket_host': '0.0.0.0',
            'server.thread_pool': max_concurrent_streams - 1,
            'server.socket_queue_size': max_concurrent_streams - 1,
            'server.accepted_queue_size': -1,
        })

        # Start the CherryPy WSGI web server
        cherrypy.engine.start()
        cherrypy.engine.block()
    elif server == 'Flask':
        app.run(host='0.0.0.0', port=5000)


def background_streaming_server():
    import multiprocessing
    process = multiprocessing.Process(target=main, name='streaming server')
    process.start()


if __name__ == '__main__':
    main()
