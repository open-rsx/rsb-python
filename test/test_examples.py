# ============================================================
#
# Copyright (C) 2018 by Johannes Wienke
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

import os
import os.path
import subprocess
import sys
import time

import pytest


_pythonpath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_example_path = os.path.join(os.path.dirname(__file__), '..', 'examples')


def _prepare_env():
    env = dict(os.environ)
    if 'PYTHONPATH' not in env:
        env['PYTHONPATH'] = ''
    env['PYTHONPATH'] = '{rsb_path}:{old}'.format(rsb_path=_pythonpath,
                                                  old=env['PYTHONPATH'])
    return env


@pytest.mark.timeout(20)
def test_listener_informer(capsys):
    with capsys.disabled():

        with subprocess.Popen(
                [sys.executable,
                 os.path.join(_example_path, 'listener.py')],
                stdout=subprocess.PIPE,
                env=_prepare_env()) as listener_proc:
            time.sleep(0.5)

            subprocess.check_call(
                [sys.executable, os.path.join(_example_path, 'informer.py')],
                env=_prepare_env())

            assert b'Received event: ' in listener_proc.stdout.read()


@pytest.mark.timeout(20)
def test_reader_informer(capsys):
    with capsys.disabled():

        with subprocess.Popen(
                [sys.executable,
                 os.path.join(_example_path, 'reader.py')],
                stdout=subprocess.PIPE,
                env=_prepare_env()) as reader_proc:
            time.sleep(0.5)

            subprocess.check_call(
                [sys.executable, os.path.join(_example_path, 'informer.py')],
                env=_prepare_env())

            assert b'Received event: ' in reader_proc.stdout.read()


@pytest.mark.timeout(20)
def test_client_server(capsys):
    with capsys.disabled():

        with subprocess.Popen(
                [sys.executable,
                 os.path.join(_example_path, 'server.py')],
                env=_prepare_env()):
            time.sleep(0.5)

            client_output = subprocess.check_output(
                [sys.executable, os.path.join(_example_path, 'client.py')],
                env=_prepare_env())

            assert client_output.count(b'server replied') == 2
