"""Test-only slow computation in a spawned process; never used by the app."""
import time
from threading import Event
from lab import worker

real_execute=worker.execute

def slow_compute(*_):
    time.sleep(60)
    return {}

def slow_execute(*args):
    worker.compute=slow_compute
    real_execute(*args)

if __name__=='__main__':
    import os
    worker.execute=slow_execute
    worker.run(timeout=float(os.environ.get('TEST_TIMEOUT','10')))
