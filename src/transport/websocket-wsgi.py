from typing import Any, OrderedDict
from common import Socket, Transport

import json


class WebSocketApplicationNotFound(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def get_gevent_websocket_app(transport: Transport):
    from geventwebsocket import WebSocketApplication

    class GeventTransportSocket(Socket):
        def emit(self, event, *args, **kwargs):
            if event == "message":
                # try to parse json
                message = args[0]

                try:
                    message = json.loads(message)
                except Exception:
                    pass

                super().emit(event, message)
                return

            super().emit(event, *args, **kwargs)

    class GeventTransportApplicatoin(WebSocketApplication):
        def __init__(self, ws):
            super().__init__(ws)

        def on_open(self):
            self.socket = GeventTransportSocket()

            transport.emit("open", self.socket)

        def on_message(self, message):
            if message is None:
                return

            transport.emit("message", message)

            self.socket.emit("message", message)

        def on_close(self, reason):
            transport.emit("close", reason)

            self.socket.emit("close", reason)

    def handler(environ, start_response):
        ws = environ["wsgi.websocket"]

        app = GeventTransportApplicatoin(ws)

        app.handle()

        return []

    return handler


def get_eventlet_websocket_app(transport: Transport):
    from eventlet.websocket import WebSocketWSGI

    def handler(ws):
        while True:
            message = ws.wait()

            if message is None:
                break

            transport.emit("message", message)

        return []

    return WebSocketWSGI(handler)


def try_get_websocket_app(transport: Transport):
    for make in [get_gevent_websocket_app, get_eventlet_websocket_app]:

        try:
            app = make(transport)
            return app
        except Exception as ex:
            # print(ex)
            pass

    raise WebSocketApplicationNotFound("websocket application not found")


class WebSocketTransport(Transport):
    def __init__(self):
        super().__init__()

    def __call__(self, environ, start_response):
        if "wsgi.websocket" in environ:
            # gevent app
            app = get_gevent_websocket_app(transport)
            app(environ, start_response)
        elif ("eventlet.input" in environ) or ("gunicorn.socket" in environ):
            app = get_eventlet_websocket_app(transport)
            app(environ, start_response)

        return []

    def emit(self, event, *args, **kwargs):
        if event == "message":
            # try to parse json
            message = args[0]

            try:
                message = json.loads(message)
            except Exception:
                pass

            super().emit(event, message)
            return

        super().emit(event, *args, **kwargs)


if __name__ == "__main__":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    from geventwebsocket import Resource

    from gevent import monkey

    monkey.patch_all()

    transport = WebSocketTransport()

    # @transport.on('open')
    # def on_open():
    #   print('connection open')

    # @transport.on('message')
    # def on_open(message):
    #   print(f'message {message}')

    # @transport.on('close')
    # def on_open(reason):
    #   print(f'connection close: {reason}')

    def on_open(socket: Socket):
        def on_message(message):
            print(f"socket[{socket.id}] message: {message}")

        socket.on("message", on_message)
        socket.on(
            "close",
            lambda reason: print(
                f"socket[{socket.id}] close: connection close: {reason}"
            ),
        )

    transport.on("open", on_open)
    transport.on("close", lambda reason: print(f"connection close: {reason}"))

    class Dispatcher:
        def __init__(self, handlers) -> None:
            self.handlers = handlers or {}

        def __call__(self, environ, start_response) -> Any:
            print(environ)
            for key, handler in self.handlers.items():
                p = environ["PATH_INFO"]

                if p.startswith(key):
                    handler(environ, start_response)

                    return []

    dispatcher = Dispatcher(
        OrderedDict(
            {
                "/ws": transport,
                "/": lambda environ, start_response: start_response(
                    "200 OK", [("Content-Type", "text/html")]
                )
                and [b"WebSocket server is running"],
            }
        )
    )

    def test(environ, _):
        print(environ)

        return []

    server = pywsgi.WSGIServer(
        ("0.0.0.0", 8000), dispatcher, handler_class=WebSocketHandler
    )

    print("Starting WebSocket server on port 8000...")
    server.serve_forever()
