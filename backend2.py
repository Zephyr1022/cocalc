"""
Backend Compute Process

Tornado + TorandIO2 application.
"""

import logging, os, sys
from tornado import web
from tornadio2 import SocketConnection, TornadioRouter, SocketServer, event

FLUSH_INTERVAL = 0.01

ROOT = os.path.abspath(os.path.normpath(os.path.dirname(__file__)))
print ROOT

class IndexHandler(web.RequestHandler):
    def get(self):
        self.render(os.path.join(ROOT, 'templates/backend_index.html'))

import time
class OutputStream(object):
    def __init__(self, f, flush_interval):
        self._f = f
        self._buf = ''
        self._last_flush = time.time()
        self._flush_interval = flush_interval

    def write(self, output):
        self._buf += output
        w = time.time()
        if w - self._last_flush >= self._flush_interval:
            self._last_flush = w
            self.flush()

    def flush(self):
        self._f(self._buf)
        self._buf = ''

namespace = {}

class ExecuteConnection(SocketConnection):
    clients = set()
    
    def on_open(self, *args, **kwargs):
        self.clients.add(self)
        print "made connection!"

    def broadcast(self, *args, **kwds):
        for c in self.clients:
            c.emit(*args, **kwds)

    def broadcast_other(self, *args, **kwds):
        for c in self.clients:
            if c != self:
                c.emit(*args, **kwds)

    @event
    def execute(self, id, code):
        so = OutputStream(lambda msg: self.emit('stdout-%s'%id, msg), FLUSH_INTERVAL)
        se = OutputStream(lambda msg: self.emit('stderr-%s'%id, msg), FLUSH_INTERVAL)
        stdout = sys.stdout; stderr = sys.stderr
        sys.stdout = so; sys.stderr = se
        try:
            exec code in namespace
        except:
            se.write(repr(sys.exc_info()[1]))
        finally:
            sys.stdout = stdout; sys.stderr = stderr
            so.flush(); se.flush()
            self.emit('done-%s'%id)

    @event
    def set(self, selector, value):
        self.broadcast('set', selector, value)

    @event
    def set_other(self, selector, value):
        self.broadcast_other('set', selector, value)
        
    @event
    def execute2(self, selector, code):
        self.set(selector, '')  # clear output
        so = OutputStream(lambda s: self.broadcast('stdout', selector, s), FLUSH_INTERVAL)
        se = OutputStream(lambda s: self.broadcast('stderr', selector, s), FLUSH_INTERVAL)
        stdout = sys.stdout; stderr = sys.stderr
        sys.stdout = so; sys.stderr = se
        try:
            exec code in namespace
        except:
            se.write(repr(sys.exc_info()[1]))
        finally:
            sys.stdout = stdout; sys.stderr = stderr
            so.flush(); se.flush()
            self.emit('done', selector)

def run(port, debug):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    router = TornadioRouter(ExecuteConnection)
    SocketServer(web.Application(
        router.apply_routes([(r"/", IndexHandler),
                             (r"/static/(.*)", web.StaticFileHandler,
                              {'path':os.path.join(ROOT ,'static')}),
                             ]),
        flash_policy_port = 843,
        flash_policy_file = os.path.join(ROOT, 'flashpolicy.xml'),
        socket_io_port = port,
        debug=debug
    ))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: %s PORT [DEBUG]"%sys.argv[0]
        sys.exit(1)
    port = int(sys.argv[1])
    if len(sys.argv) >= 3:
        debug = eval(sys.argv[2])
    else:
        debug = False
    run(port, debug)
