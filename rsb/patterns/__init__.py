# ============================================================
#
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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

import rsb

class Method (object):
    def __init__(self, server, name):
        self._server   = server
        self._name     = name
        self._listener = None
        self._informer = None

    def getName(self):
        return self._name

    name = property(getName)

    def getListener(self):
        if self._listener is None:
            self._listener = self.makeListener()
        return self._listener

    listener = property(getListener)

    def getInformer(self):
        if self._informer is None:
            self._informer = self.makeInformer()
        return self._informer

    informer = property(getInformer)

    def deactivate(self):
        if not self._informer is None:
            self._informer.deactivate()
        if not self._listener is None:
            self._listener.deactivate()

class Server (rsb.Participant):
    def __init__(self, scope):
        super(Server, self).__init__(scope)
        self._methods = {}

    def addMethod(self, method):
        self._methods[method.name] = method

    def removeMethod(self, method):
        del self._methods[method.name]

    def deactivate(self):
        map(lambda x: x.deactivate, self._methods.values())

######################################################################
#
# Local Server
#
######################################################################

class LocalServer (Server):
    def __init__(self, scope):
        super(LocalServer, self).__init__(scope)


######################################################################
#
# Remote Server
#
######################################################################

class Call (object):
    def __init__(self, id):
        self._id     = id
        self._result = None

    @property
    def getId(self):
        return self._id

    def getResult(self):
        return self._result

    def setResult(self, newValue):
        self._result = newValue

    result = property(getResult, setResult)

    def done(self):
        return not result._result is None

    def wait(self):
        pass

class RemoteMethod (Method):
    def __init__(self, server, name):
        super(RemoteMethod, self).__init__(server, name)
        self._calls = {}

    def makeListener(self):
        listener = rsb.Listener(self.server.scope
                                .concat(Scope("reply"))
                                .concat(Scope(self.name)))
        listener.addHandler(self._handleReply)

    def makeInformer(self):
        return rsb.Informer(self.server.scope
                            .concat(Scope("requst"))
                            .concat(Scope(self.name)),
                            'TODO type')

    def _handleReply(self, event):
        key = event.metaData.getUserInfo('ServerRequestId')
        call = self._calls[key]
        call.result = event.getData()

    def __call__(self, arg):
        self.listener # Force listener creation

        call = Call()
        self._calls[call.id] = call
        event = rsb.Event(metaData = { 'ServerRequestId': call.id })
        event.data = arg
        self.informer.publishEvent(event)

        with self._lock:
            while not call.done():
                call.wait()
            del self._calls[call.id]
        return call.result

class RemoteServer (Server):
    def __init__(self, scope):
        super(RemoteServer, self).__init__(scope)

    def addMethod(self, method):
        super(RemoteServer, self).addMethod(method)
        setattr(self, method.name, method)

    def removeMethod(self, method):
        #delattr(self, method.name)
        super(RemoteServer, self).removeMethod(method)
