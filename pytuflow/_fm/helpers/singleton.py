# import threading
#
#
# lock = threading.Lock()


class Singleton(type):

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            if cls not in cls._instances:
                cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# class SingletonThreadLocked(type):
#     """Base class for Singleton Types.
#
#     Initial setup will lock the constructor to avoid duplication.
#     Only one instance of each subclass can be created, it will be tracked in
#     the _instances dict.
#     """
#     _instances = {}
#
#     def __call__(cls, *args, **kwargs):
#         if cls not in cls._instances:
#             with lock:
#                 if cls not in cls._instances:
#                     cls._instances[cls] = super(SingletonThreadLocked, cls).__call__(*args, **kwargs)
#         return cls._instances[cls]
