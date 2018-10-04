# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
#
# This file may be licensed under the terms of the
# GNU Lesser General Public License Version 3 (the ``LGPL''),
# or (at your option) any later version.
#
# Software distributed under the License is distributed
# on an ``AS IS'' basis, WITHOUT WARRANTY OF ANY KIND, either
# express or implied. See the LGPL for the specific language
# governing rights and limitations.
#
# You should have received a copy of the LGPL along with this
# program. If not, go to http://www.gnu.org/licenses/lgpl.html
# or write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# The development of this software was supported by:
#   CoR-Lab, Research Institute for Cognition and Robotics
#     Bielefeld University
#
# ============================================================

"""
Various helper classes and methods.

.. codeauthor:: jwienke
"""

from threading import Lock, Condition, Thread
from queue import Queue
import logging


class Enum(object):
    """
    Generates enum-like classes in python with proper printing support.

    .. codeauthor:: jwienke
    """

    class EnumValue(object):

        def __init__(self, name, value=None):
            self.__name = name
            self.__value = value
            if self.__value is None:
                self.__value = name

        def __str__(self):
            return "%s" % (self.__name)

        def __repr__(self):
            return "%s(%r, %r)" % (self.__class__.__name__,
                                   self.__name,
                                   self.__value)

        def __eq__(self, other):
            try:
                return other.__value == self.__value
            except (AttributeError, TypeError):
                return False

        def __ne__(self, other):
            return not self.__eq__(other)

        def __lt__(self, other):
            return self.__value < other.__value

        def __le__(self, other):
            return self.__value <= other.__value

        def __gt__(self, other):
            return self.__value > other.__value

        def __ge__(self, other):
            return self.__value >= other.__value

    def __init__(self, name, keys, values=None):
        """
        Generates a new enum.

        Args:
            name:
                name of the enum to create. Will normally be the name of the
                variable this constructor call is assigned to. For Used for
                printing.
            keys:
                list of enum keys to generate
        """

        if values is not None and len(values) != len(keys):
            raise ValueError("Length of enum key list must be the same "
                             "as value list, keys: %s, values: %s"
                             % (keys, values))

        self.__name = name
        self.__keys = keys
        self.__values = values
        self.__keyString = ", ".join(keys)
        for (i, key)in enumerate(keys):
            if values:
                setattr(self, key, Enum.EnumValue(key, values[i]))
            else:
                setattr(self, key, Enum.EnumValue(key))

    def from_string(self, string):
        if string not in self.__keys:
            raise ValueError("Invalid enum item `%s'" % string)
        return getattr(self, string)

    def __str__(self):
        return "Enum %s: %s" % (self.__name, self.__keyString)

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__,
                               self.__keys,
                               self.__values)


class InterruptedError(RuntimeError):
    """
    .. codeauthor:: jwienke
    """
    pass


class OrderedQueueDispatcherPool(object):
    """
    A thread pool that dispatches messages to a list of receivers. The number
    of threads is usually smaller than the number of receivers and for each
    receiver it is guaranteed that messages arrive in the order they were
    published. No guarantees are given between different receivers.  All
    methods except #start and #stop are reentrant.

    The pool can be stopped and restarted at any time during the processing but
    these calls must be single-threaded.

    Assumptions:
     - same subscriptions for multiple receivers unlikely, hence filtering done
       per receiver thread

    .. codeauthor:: jwienke
    """

    class _Receiver(object):

        def __init__(self, receiver):
            self.receiver = receiver
            self.queue = Queue()
            self.processing = False
            self.processing_mutex = Lock()
            self.processing_condition = Condition()

    def __true_filter(self, receiver, message):
        return True

    def __init__(self, thread_pool_size, del_func, filter_func=None):
        """
        Constructs a new pool.

        Args:
            thread_pool_size (int >= 1):
                number of threads for this pool
            del_func (callable):
                the strategy used to deliver messages of type M to receivers of
                type R. This will most likely be a simple delegate function
                mapping to a concrete method call.  Must be reentrant. callable
                with two arguments. First is the receiver of a message, second
                is the message to deliver
            filter_func (callable):
                Reentrant function used to filter messages per receiver.
                Default accepts every message. callable with two arguments.
                First is the receiver of a message, second is the message to
                filter. Must return a bool, true means to deliver the message,
                false rejects it.
        """

        self.__logger = get_logger_by_class(self.__class__)

        if thread_pool_size < 1:
            raise ValueError("Thread pool size must be at least 1,"
                             "%d was given." % thread_pool_size)
        self.__thread_pool_size = int(thread_pool_size)

        self.__del_func = del_func
        if filter_func is not None:
            self.__filter_func = filter_func
        else:
            self.__filter_func = self.__true_filter

        self.__condition = Condition()
        self.__receivers = []

        self.__jobsAvailable = False

        self.__started = False
        self.__interrupted = False

        self.__threadPool = []

        self.__currentPosition = 0

    def __del__(self):
        self.stop()

    def register_receiver(self, receiver):
        """
        Registers a new receiver at the pool. Multiple registrations of the
        same receiver are possible resulting in being called multiple times for
        the same message (but effectively this destroys the guarantee about
        ordering given above because multiple message queues are used for every
        subscription).

        Args:
            receiver:
                new receiver
        """

        with self.__condition:
            self.__receivers.append(self._Receiver(receiver))

        self.__logger.info("Registered receiver %s", receiver)

    def unregister_receiver(self, receiver):
        """
        Unregisters all registration of one receiver.

        Args:
            receiver:
                receiver to unregister

        Returns:
            True if one or more receivers were unregistered, else False
        """

        removed = None
        with self.__condition:
            kept = []
            for r in self.__receivers:
                if r.receiver == receiver:
                    removed = r
                else:
                    kept.append(r)
            self.__receivers = kept
        if removed:
            with removed.processing_condition:
                while removed.processing:
                    self.__logger.info("Waiting for receiver %s to finish",
                                       receiver)
                    removed.processing_condition.wait()
        return not (removed is None)

    def push(self, message):
        """
        Pushes a new message to be dispatched to all receivers in this pool.

        Args:
            message:
                message to dispatch
        """

        with self.__condition:
            for receiver in self.__receivers:
                receiver.queue.put(message)
            self.__jobsAvailable = True
            self.__condition.notify()

        # XXX: This is disabled because it can trigger this bug for protocol
        # buffers payloads:
        # http://code.google.com/p/protobuf/issues/detail?id=454
        # See also #1331
        # self.__logger.debug("Got new message to dispatch: %s", message)

    def __next_job(self, worker_num):
        """
        Returns the next job to process for worker threads and blocks if there
        is no job.

        Args:
            worker_num:
                number of the worker requesting a new job

        Returns:
            the receiver to work on
        """

        receiver = None
        with self.__condition:

            got_job = False
            while not got_job:

                while (not self.__jobsAvailable) and (not self.__interrupted):
                    self.__logger.debug(
                        "Worker %d: no jobs available, waiting", worker_num)
                    self.__condition.wait()

                if (self.__interrupted):
                    raise InterruptedError("Processing was interrupted")

                # search the next job
                for _ in range(len(self.__receivers)):

                    self.__currentPosition = self.__currentPosition + 1
                    real_pos = self.__currentPosition % len(self.__receivers)

                    if (not self.__receivers[real_pos].processing) and \
                            (not self.__receivers[real_pos].queue.empty()):

                        receiver = self.__receivers[real_pos]
                        receiver.processing = True
                        got_job = True
                        break

                if not got_job:
                    self.__jobsAvailable = False

            self.__condition.notify()
            return receiver

    def __finished_work(self, receiver, worker_num):

        with self.__condition:

            with receiver.processing_condition:
                receiver.processing = False
                receiver.processing_condition.notifyAll()
            if not receiver.queue.empty():
                self.__jobsAvailable = True
                self.__logger.debug("Worker %d: new jobs available, "
                                    "notifying one", worker_num)
                self.__condition.notify()

    def __worker(self, worker_num):
        """
        Threaded worker method.

        Args:
            worker_num:
                number of this worker thread
        """

        try:

            while True:

                receiver = self.__next_job(worker_num)
                message = receiver.queue.get(True, None)
                self.__logger.debug(
                    "Worker %d: got message %s for receiver %s",
                    worker_num, message, receiver.receiver)
                if self.__filter_func(receiver.receiver, message):
                    self.__logger.debug(
                        "Worker %d: delivering message %s for receiver %s",
                        worker_num, message, receiver.receiver)
                    self.__del_func(receiver.receiver, message)
                    self.__logger.debug(
                        "Worker %d: delivery for receiver %s finished",
                        worker_num, receiver.receiver)
                self.__finished_work(receiver, worker_num)

        except InterruptedError:
            pass

    def start(self):
        """
        Non-blocking start.

        Raises:
            RuntimeError:
                if the pool was already started and is running
        """

        with self.__condition:

            if self.__started:
                raise RuntimeError("Pool already running")

            self.__interrupted = False

            for i in range(self.__thread_pool_size):
                worker = Thread(target=self.__worker, args=[i])
                worker.setDaemon(True)
                worker.start()
                self.__threadPool.append(worker)

            self.__started = True

        self.__logger.info("Started pool with %d threads",
                           self.__thread_pool_size)

    def stop(self):
        """
        Blocking until every thread has stopped working.
        """

        self.__logger.info(
            "Starting to stop thread pool by wating for workers")

        with self.__condition:
            self.__interrupted = True
            self.__condition.notifyAll()

        for worker in self.__threadPool:
            self.__logger.debug("Joining worker %s", worker)
            worker.join()

        self.__threadPool = []

        self.__started = False

        self.__logger.info("Stopped thread pool")


def get_logger_by_class(klass):
    """
    Get a python logger instance based on a class instance. The logger name
    will be a dotted string containing python module and class name.

    Args:
        klass:
            class instance

    Returns:
        logger instance
    """
    return logging.getLogger(klass.__module__ + "." + klass.__name__)


def time_to_unix_microseconds(time):
    """
    Converts a floating point, seconds based time to a unix timestamp in
    microseconds precision.

    Args:
        time:
            time since epoch in seconds + fractional part.

    Returns:
        time as integer with microseconds precision.
    """
    return int(time * 1000000)


def unix_microseconds_to_time(value):
    return float(value) / 1000000.0


def prefix():
    """
    Tries to return the prefix that this code was installed into by guessing
    the install location from some rules.

    Adapted from
    http://ttboj.wordpress.com/2012/09/20/finding-your-software-install-prefix-from-inside-python/

    Returns:
        string path with the install prefix or empty string if not known
    """

    import os
    import sys

    path = os.path.abspath(__file__)
    token = "dummy"

    while len(token) > 0:
        (path, token) = os.path.split(path)
        if token in ['site-packages', 'dist-packages']:
            (path, token) = os.path.split(path)
            if token == 'python%s' % sys.version[:3]:
                (path, token) = os.path.split(path)
                return path

    return ""
