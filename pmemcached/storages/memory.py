from .base import BaseStorage


class Storage(BaseStorage):
    def __init__(self):
        super(Storage, self).__init__()
        self.data = {}

    def expire_key(self, key):
        if key in self.data:
            del self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        super(Storage, self).__setitem__(key, value)

    def __getitem__(self, key):
        return self.data[key]

    def __delitem__(self, key):
        del self.data[key]
