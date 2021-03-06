# The MIT License (MIT)
#
# Copyright (c) 2018 Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import errno
import os
import weakref


class nullable_ref(object):
  '''
  A weak-reference type that can represent #None.
  '''

  def __init__(self, obj):
    self.set(obj)

  def __repr__(self):
    return '<nullable_ref to {!r}>'.format(self())

  def __call__(self):
    if self._ref is not None:
      return self._ref()
    return None

  def __bool__(self):
    return self._ref is not None

  __nonzero__ = __bool__

  def set(self, obj):
    self._ref = weakref.ref(obj) if obj is not None else None


def makedirs(path, raise_on_exists=False):
  '''
  Like #os.makedirs(), but by default this function does not raise an
  exception if the directory already exists.
  '''

  try:
    os.makedirs(path)
  except OSError as exc:
    if raise_on_exists or exc.errno != errno.EEXIST:
      raise
