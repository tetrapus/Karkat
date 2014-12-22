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
        self._safe_mutate = False
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

    def updater(self):
        return ConfigUpdater(self)

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
    def __sizeof__(self, *args, **kwargs): 
        return self.data.__sizeof__(*args, **kwargs)
    @_locked
    def __lt__(self, *args, **kwargs): 
        return self.data.__lt__(*args, **kwargs)
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



class ConfigUpdater(object):
    def __init__(self, config):
        self.config = config

    def __enter__(self):
        self.config.mutex.acquire()
        return self

    def __exit__(self, ty, value, traceback):
        if ty is None:
            self.config._save()
        self.config.mutex.release()
        
    def __len__(self, *args, **kwargs): 
        return self.config.data.__len__(*args, **kwargs)
    def copy(self, *args, **kwargs): 
        return self.config.data.copy(*args, **kwargs)
    def __hash__(self, *args, **kwargs): 
        return self.config.data.__hash__(*args, **kwargs)
    def update(self, *args, **kwargs): 
        return self.config.data.update(*args, **kwargs)
    def values(self, *args, **kwargs): 
        return self.config.data.values(*args, **kwargs)
    def __iter__(self, *args, **kwargs): 
        return self.config.data.__iter__(*args, **kwargs)
    def __delitem__(self, *args, **kwargs): 
        return self.config.data.__delitem__(*args, **kwargs)
    def pop(self, *args, **kwargs): 
        return self.config.data.pop(*args, **kwargs)
    def __repr__(self, *args, **kwargs): 
        return self.config.data.__repr__(*args, **kwargs)
    def __ne__(self, *args, **kwargs): 
        return self.config.data.__ne__(*args, **kwargs)
    def __setitem__(self, *args, **kwargs): 
        return self.config.data.__setitem__(*args, **kwargs)
    def popitem(self, *args, **kwargs): 
        return self.config.data.popitem(*args, **kwargs)
    def keys(self, *args, **kwargs): 
        return self.config.data.keys(*args, **kwargs)
    def __gt__(self, *args, **kwargs): 
        return self.config.data.__gt__(*args, **kwargs)
    def items(self, *args, **kwargs): 
        return self.config.data.items(*args, **kwargs)
    def __sizeof__(self, *args, **kwargs): 
        return self.config.data.__sizeof__(*args, **kwargs)
    def setdefault(self, *args, **kwargs): 
        return self.config.data.setdefault(*args, **kwargs)
    def __lt__(self, *args, **kwargs): 
        return self.config.data.__lt__(*args, **kwargs)
    def get(self, *args, **kwargs): 
        return self.config.data.get(*args, **kwargs)
    def fromkeys(self, *args, **kwargs): 
        return self.config.data.fromkeys(*args, **kwargs)
    def clear(self, *args, **kwargs): 
        return self.config.data.clear(*args, **kwargs)
    def __eq__(self, *args, **kwargs): 
        return self.config.data.__eq__(*args, **kwargs)
    def __le__(self, *args, **kwargs): 
        return self.config.data.__le__(*args, **kwargs)
    def __ge__(self, *args, **kwargs): 
        return self.config.data.__ge__(*args, **kwargs)
    def __contains__(self, *args, **kwargs): 
        return self.config.data.__contains__(*args, **kwargs)
    def __getitem__(self, *args, **kwargs): 
        return self.config.data.__getitem__(*args, **kwargs)
