import os_process
from base_process import Process
from thread_process import ThreadProcess
import logging
import os
log = logging.getLogger(__name__)

_main = None

class LazyMain(Process):
	def __getattribute__(self, attr):
		return getattr(_init_main(), attr)

	def __setattr__(self, attr, val):
		setattr(_init_main(), attr, val)
	
	def __repr__(self): return "<#Process: __main__>"
	def __str__(self): return "__main__"
	def __reduce__(self):
		return _init_main().__reduce__()

main = LazyMain()

def _init_main():
	global _main
	if _main is None:
		_main = MainProcess()
	return _main

class MainProcess(ThreadProcess):
	pid = None
	def __init__(self):
		import threading
		self._lock = threading.Lock()
		if MainProcess.pid is None:
			MainProcess.pid = os.getpid()
		else:
			raise NotMainProcessError(MainProcess.pid)
		self._register_in_global_thread_list()
		super(MainProcess, self).__init__(target=lambda x: None, link=None, name='__main__', daemon=False, args=(), kwargs={})

	def _receive(self, msg):
		"""the main thread is the only process whose
		receiver set can be modified by other threads, and therefore
		requires a lock
		"""
		with self._lock:
			super(MainProcess, self)._receive(msg)
	
	def wait(self, timeout=None):
		super(MainProcess, self).wait(timeout)
		self._reset()
	
	def _exit(self, cause):
		super(MainProcess, self)._exit(cause)
		os_process._kill_children(self, cause)

	def _reset(self):
		"""really only makes sense for tests"""
		log.debug("resetting..")
		self._error_dict = None
		global _main
		_main = None
		MainProcess.pid = None

class NotMainProcessError(RuntimeError):
	def __str__(self):
		initial_pid, = self.args
		this_pid = os.getpid()
		return "pid %s is not the main process (%s)" % (this_pid, initial_pid)

