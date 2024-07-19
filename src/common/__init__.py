import sys
from threading import RLock


class EventEmmiter:
    def __init__(self):
        self.listeners: dict[str, list] = {}

    def on(self, event: str, listener=None):
        if listener is not None:
            if event not in self.listeners:
                self.listeners[event] = []

            self.listeners[event].append(listener)

            return

        def decorator(listener):
            if event not in self.listeners:
                self.listeners[event] = []

            self.listeners[event].append(listener)

        return decorator

    def emit(self, event, *args, **kwargs):
        if event not in self.listeners:
            return

        for listener in self.listeners[event]:
            listener(*args, **kwargs)


class Transport(EventEmmiter):
    def __init__(self):
        super().__init__()


class Socket(EventEmmiter):
    __id_lock = RLock()
    __id_count = 0

    def __init__(self):
        super().__init__()

        self.__get_id()

    def __get_id(self):
        with Socket.__id_lock:
            Socket.__id_count = (Socket.__id_count + 1) % sys.maxsize

            self.id = Socket.__id_count
