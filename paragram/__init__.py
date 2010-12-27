from process import Process, Exit
from process.main import main
from process.os_process import OSProcess
from process.thread_process import ThreadProcess
from pattern import Any, etc
default_type = OSProcess

from graph import graph, enable_graphs

import logging
class NullHandler(logging.Handler):
	def emit(self, record):
		pass
h = NullHandler()
logging.getLogger("paragram").addHandler(h)
