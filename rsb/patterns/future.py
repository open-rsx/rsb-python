# ============================================================
#
# Copyright (C) 2011-2017 Jan Moringen
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
# ============================================================

"""
Contains an implementation of the future pattern.

.. codeauthor:: jmoringe
"""

import threading


class FutureError(RuntimeError):
    def __init__(self, *args):
        super().__init__(*args)


class FutureTimeout(FutureError):
    def __init__(self, *args):
        super().__init__(*args)


class FutureExecutionError(FutureError):
    def __init__(self, *args):
        super().__init__(*args)


class Future:
    """
    Represents the results of in-progress operations.

    Methods of this class allow checking the state of the represented
    operation, waiting for the operation to finish and retrieving the
    result of the operation.

    .. todo::

       Support Python's native future protocol?

    .. codeauthor:: jmoringe

    See Also:
        <http://docs.python.org/dev/library/concurrent.futures.html>_
    """

    def __init__(self):  # noqa: D200 false positive from sphinx markup
        """
        Create a new :obj:`Future` object.
        """
        self._error = False
        self._result = None

        self._lock = threading.Lock()
        self._condition = threading.Condition(lock=self._lock)

    @property
    def done(self):
        """
        Check whether the represented operation is still in progress.

        Returns:
            bool:
                ``True`` is the represented operation finished successfully or
                failed.
        """
        with self._lock:
            return self._result is not None

    def get(self, timeout=0):
        """
        Try to obtain and return the result of the represented operation.

        If necessary, wait for the operation to complete, and then
        retrieve its result.

        Args:
            timeout (float, optional):
                The amount of time in seconds in which the operation has to
                complete.

        Returns:
            The result of the operation if it did complete successfully.

        Raises:
            FutureExecutionException:
                If the operation represented by the Future object failed.
            FutureTimeoutException:
                If the result does not become available within the amount of
                time specified via ``timeout``.
        """
        with self._lock:
            while self._result is None:
                if timeout <= 0:
                    self._condition.wait()
                else:
                    self._condition.wait(timeout=timeout)
                    if self._result is None:
                        raise FutureTimeout(
                            'Timeout while waiting for result; '
                            'Waited {} seconds.'.format(timeout))

        if self._error:
            raise FutureExecutionError(
                'Failed to execute operation: {}'.format(self._result))

        return self._result

    def set_result(self, result):
        """
        Set the result and notify all waiting consumers.

        Sets the result of the :obj:`Future` to ``result`` and wakes all
        threads waiting for the result.

        Args:
            result:
                The result of the :obj:`Future` object.
        """
        with self._lock:
            self._result = result
            self._condition.notifyAll()

    def set_error(self, message):
        """
        Indicate a failure and notify all waiting consumers.

        Mark the operation represented by the :obj:`Future` object as
        failed, set ``message`` as the error message and notify all
        threads waiting for the result.

        Args:
            message (str):
                An error message that explains why/how the operation failed.
        """
        with self._lock:
            self._result = message
            self._error = True
            self._condition.notify()

    def __str__(self):
        with self._lock:
            if self._result is None:
                state = 'running'
            elif self._error:
                state = 'failed'
            else:
                state = 'completed'
        return '<{} {} at 0x{:x}>'.format(type(self).__name__, state, id(self))

    def __repr__(self):
        return str(self)


class DataFuture(Future):
    """
    A :obj:`Future` that automatically returns the payload of an :obj:`Event`.

    Instances of this class are like ordinary :obj:`Future`s, the only
    difference being that the :obj:`get` method returns the payload of an
    :obj:`Event` object.

    .. codeauthor:: jmoringe
    """

    def get(self, timeout=0):
        return super().get(timeout=timeout).data
