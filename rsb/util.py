# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
#
# This program is free software; you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation;
# either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# ============================================================

from threading import Lock, Condition, Thread
from Queue import Queue
import logging
import os
import ConfigParser

class Enum(object):
    """
    Generates enum-like classes in python with proper printing support.

    @author: jwienke
    """

    class EnumValue(object):

        def __init__(self, name, value=None):
            self.__name = name
            self.__value = value
            if self.__value == None:
                self.__value = name

        def __str__(self):
            return "%s" % (self.__name)

        def __repr__(self):
            return "%s(%r, %r)" % (self.__class__.__name__, self.__name, self.__value)

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

        @param name: name of the enum to create. Will normally be the name of
                     the variable this constructor call is assigned to. For
                     Used for printing.
        @param keys: list of enum keys to generate
        """

        if values != None and len(values) != len(keys):
            raise ValueError("Length of enum key list must be the same as value list, keys: %s, values: %s" % (keys, values))

        self.__name = name
        self.__keys = keys
        self.__values = values
        self.__keyString = ", ".join(keys)
        for i in range(len(keys)):
            if values:
                setattr(self, keys[i], Enum.EnumValue(keys[i], values[i]))
            else:
                setattr(self, keys[i], Enum.EnumValue(keys[i]))

    def __str__(self):
        return "Enum %s: %s" % (self.__name, self.__keyString)

    def __repr__(self):
        return '%s(%r, %r, %r)' % (self.__class__.__name__, self.__keys, self.__values)

class InterruptedError(RuntimeError):
    """
    Exception class indicating the interruption of a blocking or long-running
    method.

    @author: jwienke
    """
    pass

class OrderedQueueDispatcherPool(object):
    """
    A thread pool that dispatches messages to a list of receivers. The number of
    threads is usually smaller than the number of receivers and for each
    receiver it is guaranteed that messages arrive in the order they were
    published. No guarantees are given between different receivers.
    All methods except #start and #stop are reentrant.

    The pool can be stopped and restarted at any time during the processing but
    these calls must be single-threaded.

    Assumptions:
     - same subscriptions for multiple receivers unlikely, hence filtering done
       per receiver thread

    @author: jwienke
    """

    class __Receiver(object):

        def __init__(self, receiver):
            self.receiver = receiver
            self.queue = Queue()
            self.processing = False
            self.processingMutex = Lock()

    def __trueFilter(self, receiver, message):
        return True

    def __init__(self, threadPoolSize, delFunc, filterFunc=None):
        """
        Constructs a new pool.

        @type threadPoolSize: int >= 1
        @param threadPoolSize: number of threads for this pool
        @type delFunc: callable with two arguments. First is the receiver
                       of a message, second is the message to deliver
        @param delFunc: the strategy used to deliver messages of type M to
                       receivers of type R. This will most likely be a simple
                       delegate function mapping to a concrete method call. Must
                       be reentrant.
        @type filterFunc: callable with two arguments. First is the receiver
                          of a message, second is the message to filter. Must
                          return a bool, true means to deliver the message,
                          false rejects it.
        @param filterFunc: Reentrant function used to filter messages per
                          receiver. Default accepts every message.
        """

        self.__logger = getLoggerByClass(self.__class__)

        if threadPoolSize < 1:
            raise ValueError("Thread pool size must be at least 1, %d was given." % threadPoolSize)
        self.__threadPoolSize = int(threadPoolSize)

        self.__delFunc = delFunc;
        if filterFunc != None:
            self.__filterFunc = filterFunc
        else:
            self.__filterFunc = self.__trueFilter

        self.__condition = Condition()
        self.__receivers = []

        self.__jobsAvailable = False

        self.__started = False
        self.__interrupted = False

        self.__threadPool = []

        self.__currentPosition = 0

    def __del__(self):
        self.stop()

    def registerReceiver(self, receiver):
        """
        Registers a new receiver at the pool. Multiple registrations of the same
        receiver are possible resulting in being called multiple times for the
        same message (but effectively this destroys the guarantee about ordering
        given above because multiple message queues are used for every
        subscription).

        @param receiver: new receiver
        """

        with self.__condition:
            self.__receivers.append(self.__Receiver(receiver))

        self.__logger.info("Registered receiver %s" % receiver)

    def unregisterReceiver(self, receiver):
        """
        Unregisters all registration of one receiver.

        @param receiver: receiver to unregister
        @rtype: bool
        @return: True if one or more receivers were unregistered, else False
        """

        with self.__condition:
            oldSize = len(self.__receivers)
            self.__receivers = [r for r in self.__receivers if r.receiver != receiver]
            self.__logger.info("Unregistered receiver %s %d times." % (receiver, oldSize - len(self.__receivers)))
            return oldSize != len(self.__receivers)

    def push(self, message):
        """
        Pushes a new message to be dispatched to all receivers in this pool.

        @param message: message to dispatch
        """

        with self.__condition:
            for receiver in self.__receivers:
                receiver.queue.put(message)
            self.__jobsAvailable = True
            self.__condition.notify()

        self.__logger.debug("Got new message to dispatch: %s" % message)

    def __nextJob(self, workerNum):
        """
        Returns the next job to process for worker threads and blocks if there
        is no job.

        @param workerNum: number of the worker requesting a new job
        @return the receiver to work on
        """

        receiver = None
        with self.__condition:

            gotJob = False
            while not gotJob:

                while (not self.__jobsAvailable) and (not self.__interrupted):
                    self.__logger.debug("Worker %d: no jobs available, waiting" % (workerNum))
                    self.__condition.wait()

                if (self.__interrupted):
                    raise InterruptedError("Processing was interrupted")

                # search the next job
                for i in range(len(self.__receivers)):

                    self.__currentPosition = self.__currentPosition + 1
                    realPos = self.__currentPosition % len(self.__receivers)

                    if (not self.__receivers[realPos].processing) and (not self.__receivers[realPos].queue.empty()):

                        receiver = self.__receivers[realPos];
                        receiver.processing = True
                        gotJob = True
                        break

                if not gotJob:
                    self.__jobsAvailable = False

            self.__condition.notify()
            return receiver

    def __finishedWork(self, receiver, workerNum):

        with self.__condition:

            receiver.processing = False
            if not receiver.queue.empty():
                self.__jobsAvailable = True
                self.__logger.debug("Worker %d: new jobs available, notifying one" % (workerNum))
                self.__condition.notify()

    def __worker(self, workerNum):
        """
        Threaded worker method.

        @param workerNum: number of this worker thread
        """

        try:

            while True:

                receiver = self.__nextJob(workerNum)
                message = receiver.queue.get(True, None)
                self.__logger.debug("Worker %d: got message %s for receiver %s" % (workerNum, message, receiver.receiver))
                if self.__filterFunc(receiver.receiver, message):
                    self.__logger.debug("Worker %d: delivering message %s for receiver %s" % (workerNum, message, receiver.receiver))
                    self.__delFunc(receiver.receiver, message)
                    self.__logger.debug("Worker %d: delivery for receiver %s finished" % (workerNum, receiver.receiver))
                self.__finishedWork(receiver, workerNum)

        except InterruptedError:
            pass

    def start(self):
        """
        Non-blocking start.

        @raise RuntimeError: if the pool was already started and is running
        """

        with self.__condition:

            if self.__started:
                raise RuntimeError("Pool already running")

            self.__interrupted = False

            for i in range(self.__threadPoolSize):
                worker = Thread(target=self.__worker, args=[i])
                worker.setDaemon(True)
                worker.start()
                self.__threadPool.append(worker)

            self.__started = True

        self.__logger.info("Started pool with %d threads" % self.__threadPoolSize)

    def stop(self):
        """
        Blocking until every thread has stopped working.
        """

        self.__logger.info("Starting to stop thread pool by wating for workers")

        with self.__condition:
            self.__interrupted = True
            self.__condition.notifyAll()

        for worker in self.__threadPool:
            self.__logger.debug("Joining worker %s " % worker)
            worker.join()

        self.__threadPool = []

        self.__started = False

        self.__logger.info("Stopped thread pool")

def getLoggerByClass(klass):
    return logging.getLogger(klass.__module__ + "." + klass.__name__)

class ParticipantConfig (object):
    class Transport (object):
        def __init__(self, name, options={}):
            self._name = name
            self._enabled = options.get('enabled', '1') == 1
            self._options = dict([ (key, value) for (key, value) in options.items()
                                   if not '.' in key and not key == 'enabled' ])

        def getOptions(self):
            return self._options

        def __str__(self):
            return ('ParticipantConfig.Transport[%s, enabled = %s,  %s]'
                    % (self._name, self._enabled, self._options))

        def __repr__(self):
            return str(self)

    def __init__(self, transports={}, options={}):
        self._transports = transports
        self._options = options

    def getTransport(self, name):
        return self._transports[name]

    def __str__(self):
        return 'ParticipantConfig[%s %s]' % (self._transports.values(), self._options)

    def __repr__(self):
        return str(self)

    @classmethod
    def _fromDict(clazz, options):
        def sectionOptions(section):
            return [ (key[len(section) + 1:], value) for (key, value) in options.items()
                     if key.startswith(section) ]
        result = ParticipantConfig()
        for transport in [ 'spread' ]:
            options = dict(sectionOptions('transport.%s' % transport))
            result._transports[transport] = clazz.Transport(transport, options)
        return result

    @classmethod
    def _fromFile(clazz, path, defaults={}):
        parser = ConfigParser.RawConfigParser()
        parser.read(path)
        options = defaults
        for section in parser.sections():
            for (k, v) in parser.items(section):
                options[section + '.' + k] = v
        return options

    @classmethod
    def fromFile(clazz, path, defaults={}):
        '''
        Obtain configuration options from the configuration file @a
        path, store them in a @ref ParticipantConfig object and return
        it.

        A simple configuration file may look like this:
        @verbatim
        [transport.spread]
        host = azurit # default type is string
        port = 5301 # types can be specified in angle brackets
        # A comment
        @endverbatim

        @param path File of path
        @param defaults  defaults
        @return

        @see fromEnvironment, fromDefaultSources
        '''
        return clazz._fromDict(clazz._fromFile(path, defaults))

    @classmethod
    def _fromEnvironment(clazz, defaults={}):
        options = defaults
        for (key, value) in os.environ.items():
            if key.startswith('RSB_'):
                options[key[4:].lower().replace('_', '.')] = value
        return options

    @classmethod
    def fromEnvironment(clazz, defaults={}):
        '''
        Obtain configuration options from environment variables, store
        them in a @ref ParticipantConfig object and return
        it. Environment variable names are mapped to RSB option names
        as illustrated in the following example:

        @verbatim
        RSB_TRANSPORT_SPREAD_PORT -> transport spread port
        @endverbatim

        @param defaults A @ref ParticipantConfig object that supplies
        values for configuration options for which no environment
        variables are found.
        @return A @ref ParticipantConfig object that contains the
        merged configuration options from @a defaults and relevant
        environment variables.

        @see fromFile, fromDefaultSources
        '''
        return clazz._fromDict(clazz._fromEnvironment(defaults))

    @classmethod
    def fromDefaultSources(clazz, defaults={}):
          '''
          Obtain configuration options from multiple sources, store
          them in a @ref ParticipantConfig object and return it. The
          following sources of configuration information will be
          consulted:

          -# ~/.config/rsb.conf
          -# \$(PWD)/rsb.conf
          -# Environment Variables

          @param defaults A @ref ParticipantConfig object the options
          of which should be used as defaults.

          @return A @ref ParticipantConfig object that contains the
          merged configuration options from the sources mentioned
          above.

          @see fromFile, fromEnvironment
          '''
          partial = clazz._fromFile(os.path.expanduser("~/.config/rsb.conf"))
          partial = clazz._fromFile("rsb.conf", partial)
          options = clazz._fromEnvironment(partial)
          return clazz._fromDict(options)
