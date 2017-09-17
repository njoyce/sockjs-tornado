from heapq import heappush, heappop
import time

from tornado import ioloop

from sockjs.tornado.log import pool as LOG


__all__ = [
    'SessionPool',
]


class SessionPool(object):
    """
    A garbage collected Session Pool.
    """

    def __init__(self, gc_delay, heartbeat_delay):
        self.stopping = False
        self.sessions = {}
        self.cycles = {}

        self.pool = []

        self.gc_periodic_callback = ioloop.PeriodicCallback(
            self.gc,
            gc_delay * 1000
        )
        self.heartbeat_periodic_callback = ioloop.PeriodicCallback(
            self.heartbeat,
            heartbeat_delay * 1000,
        )

    def set_gc_delay(self, delay):
        self.gc_periodic_callback.callback_time = delay * 1000

    def set_heartbeat_delay(self, delay):
        self.heartbeat_periodic_callback.callback_time = delay * 1000

    def __str__(self):
        return str(self.sessions)

    def __del__(self):
        try:
            self.stop()
        except:
            pass

    def start(self):
        """
        Start the session pool garbage collector. This is broken out into a
        separate function to give you more granular control on the context this
        thread is spawned in.
        """
        self.stopping = False
        self.sessions = {}
        self.cycles = {}

        self.pool = []

        if not self.gc_periodic_callback.is_running():
            self.gc_periodic_callback.start()

        if not self.heartbeat_periodic_callback.is_running():
            self.heartbeat_periodic_callback.start()

    def stop(self):
        """
        Manually expire all sessions in the pool.
        """
        if self.stopping:
            return

        self.stopping = True

        self.gc_periodic_callback.stop()
        self.heartbeat_periodic_callback.stop()

        try:
            self.drain()
        finally:
            self.pool = None
            self.cycles = None
            self.sessions = None

    def drain(self):
        while self.pool:
            _, session = heappop(self.pool)

            if not session.closed:
                session.close()

    def add(self, session, time_func=time.time):
        if self.stopping:
            raise RuntimeError('SessionPool is stopping')

        if session.session_id in self.sessions:
            raise RuntimeError('Adding already existing session %r' % (
                session.session_id,
            ))

        if not session.new:
            raise RuntimeError('Session has already expired')

        current_time = self.cycles[session] = time_func()
        self.sessions[session.session_id] = session

        heappush(self.pool, (current_time, session))

    def get(self, session_id):
        """
        Get active sessions by their session id.
        """
        return self.sessions.get(session_id, None)

    def remove(self, session_id):
        session = self.sessions.pop(session_id, None)

        if not session:
            return False

        current_time = self.cycles.pop(session, None)

        if current_time:
            try:
                self.pool.remove((current_time, session))
            except ValueError:
                pass

        try:
            session.close()
        except Exception:
            LOG.exception('Failed to close session %r', session)

        return True

    def gc(self, time_func=time.time):
        """
        Rearrange the heap flagging active sessions with the id of this
        collection iteration. This data-structure is time-independent so we
        sessions can be added to and from without the need to lock the pool.
        """
        if not self.pool:
            return

        current_time = time_func()

        while self.pool:
            session = self.pool[0][1]
            cycle = self.cycles[session]

            if cycle >= current_time:
                # we've looped through all sessions
                break

            last_checked, session = heappop(self.pool)

            if session.has_expired(current_time):
                # Session is to be GC'd immediately
                self.remove(session.session_id)

                continue

            # Flag the session with the id of this GC cycle
            self.cycles[session] = current_time
            heappush(self.pool, (current_time, session))

    def heartbeat(self, time_func=time.time):
        """
        Send a heartbeat ping to all the connected sessions.
        """
        for session in self.sessions.values():
            session.send_heartbeat()
