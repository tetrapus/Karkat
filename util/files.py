import json
import os
from functools import wraps
from threading import Lock


def _locked(function):
    @wraps(function)
    def _(self, *args, **kwargs):
        with self.mutex:
            function(self, *args, **kwargs)
    return _

def _updater(function):
    @wraps(function)
    def _(self, *args, **kwargs):
        with self.mutex:
            function(self, *args, **kwargs)
            self._save()
    return _    

class Config(object):
    def __init__(self, filename, default=None):
        self.mutex = Lock()
        self.filename = filename
        if default is None:
            default = {}
        try:
            with open(filename) as file_:
                self.data = json.load(file_)
        except OSError:
            self.data = default

    def save(self):
        with self.mutex:
            self.save()

    def __enter__(self):
        self.mutex.acquire()
        return self.data

    def __exit__(self, ty, value, traceback):
        if ty is None:
            self._save()
        self.mutex.release()

    # Unsafe functions

    def _save(self):
        tempfn = self.filename + ".tmp"
        with open(tempfn, "x") as tempfile:
            json.dump(self.data, tempfile)
            tempfile.flush()
            os.fsync(tempfile.fileno())
        os.rename(tempfn, self.filename)

    # Wrappers
    @_locked
    def __len__(self, *args, **kwargs): 
        return self.data.__len__(*args, **kwargs)
    @_locked
    def copy(self, *args, **kwargs): 
        return self.data.copy(*args, **kwargs)
    @_locked
    def __hash__(self, *args, **kwargs): 
        return self.data.__hash__(*args, **kwargs)
    @_updater
    def update(self, *args, **kwargs): 
        return self.data.update(*args, **kwargs)
    @_locked
    def values(self, *args, **kwargs): 
        return self.data.values(*args, **kwargs)
    @_locked
    def __iter__(self, *args, **kwargs): 
        return self.data.__iter__(*args, **kwargs)
    @_updater
    def __delitem__(self, *args, **kwargs): 
        return self.data.__delitem__(*args, **kwargs)
    @_updater
    def pop(self, *args, **kwargs): 
        return self.data.pop(*args, **kwargs)
    @_locked
    def __repr__(self, *args, **kwargs): 
        return self.data.__repr__(*args, **kwargs)
    @_locked
    def __ne__(self, *args, **kwargs): 
        return self.data.__ne__(*args, **kwargs)
    @_updater
    def __setitem__(self, *args, **kwargs): 
        return self.data.__setitem__(*args, **kwargs)
    @_updater
    def popitem(self, *args, **kwargs): 
        return self.data.popitem(*args, **kwargs)
    @_locked
    def keys(self, *args, **kwargs): 
        return self.data.keys(*args, **kwargs)
    @_locked
    def __gt__(self, *args, **kwargs): 
        return self.data.__gt__(*args, **kwargs)
    @_locked
    def items(self, *args, **kwargs): 
        return self.data.items(*args, **kwargs)
    @_locked
    def __sizeof__(self, *args, **kwargs): 
        return self.data.__sizeof__(*args, **kwargs)
    @_updater
    def setdefault(self, *args, **kwargs): 
        return self.data.setdefault(*args, **kwargs)
    @_locked
    def __lt__(self, *args, **kwargs): 
        return self.data.__lt__(*args, **kwargs)
    @_locked
    def get(self, *args, **kwargs): 
        return self.data.get(*args, **kwargs)
    @_updater
    def clear(self, *args, **kwargs): 
        return self.data.clear(*args, **kwargs)
    @_locked
    def __eq__(self, *args, **kwargs): 
        return self.data.__eq__(*args, **kwargs)
    @_locked
    def __le__(self, *args, **kwargs): 
        return self.data.__le__(*args, **kwargs)
    @_locked
    def __ge__(self, *args, **kwargs): 
        return self.data.__ge__(*args, **kwargs)
    @_locked
    def __contains__(self, *args, **kwargs): 
        return self.data.__contains__(*args, **kwargs)
    @_locked
    def __getitem__(self, *args, **kwargs): 
        return self.data.__getitem__(*args, **kwargs)


