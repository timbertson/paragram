import process
import logging
import os
log = logging.getLogger(__name__)

_main = None

class LazyMain(process.Process):
	def __getattr__(self, attr):
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
		print repr(_main)
	return _main

class MainProcess(process.ThreadProcess):
	pid = None
	def __init__(self):
		import threading
		self._lock = threading.Lock()
		if MainProcess.pid is None:
			MainProcess.pid = os.getpid()
		else:
			raise RuntimeError("pid %s is not the initial process (%s)" % (os.getpid(), MainProcess.pid))
		super(MainProcess, self).__init__(target=lambda x: None, link=None, name='__main__', daemon=False)

	def _receive(self, msg):
		"""the main thread is the only process whose
		receiver pool can be modified by other threads, and therefore
		requires a lock
		"""
		with self._lock:
			super(MainProcess, self)._receive(msg)
	
	def wait(self, timeout=None):
		super(MainProcess, self).wait(timeout)
		self._reset()
	
	def _exit(self):
		super(MainProcess, self)._exit()
		process._kill_children(self)

	def _reset(self):
		"""really only makes sense for tests"""
		log.debug("resetting..")
		global _main
		_main = None
		MainProcess.pid = None


