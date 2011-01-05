"""
Processes
---------

.. autoclass:: paragram.Process
	:members:

.. autoclass:: paragram.process.base_process.LocalProcess
	:members:

.. data:: OSProcess

	A paragram process implemented as a separate operating system process.

.. data:: ThreadProcess

	A paragram process implemented as a new thread in the current
	OS process.

See also: :ref:`handling_messages`

Constants
------------------

.. data:: Any

	Matches any object


.. data:: etc

	Matches any remaining objects in a tuple or list

.. data:: main

	A fake paragram process representing the main thread of control. This
	should not be directly referenced by anything but the main thread - if
	another process needs to talk to the main process, it should be sent a
	reference to this object in a message rather than accessing it directly.

"""
from process import Process, Exit
from process.main import main
from process.os_process import OSProcess
from process.thread_process import ThreadProcess
from pattern import Any, etc
default_type = ThreadProcess

from graph import graph, enable_graphs

import logging
class NullHandler(logging.Handler):
	def emit(self, record):
		pass
h = NullHandler()
logging.getLogger("paragram").addHandler(h)
