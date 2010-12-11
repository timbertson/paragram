import process
import logging
log = logging.getLogger(__name__)

_main = None

class LazyMain(process.Process):
	def __getattr__(self, attr):
		return getattr(_init_main(), attr)

	def __setattr__(self, attr, val):
		setattr(_init_main(), attr, val)
	
	def __repr__(self): return "<#Process: __main__>"
	def __str__(self): return "__main__"

#TODO: should this only ever be accessible from the first process?
main = LazyMain()

def _set_foreign_main(proc):
	global _main
	_main = MainProcess(proc)

def _init_main():
	global _main
	if _main is None:
		_main = MainProcess()
	return _main

class MainProcess(process.Process):
	_denied_remote_attrs = ('receive','spawn')
	def __init__(self, proc=None):
		self.remote = proc is not None
		if proc is None:
			self._proc = ExistingProcess()
		else:
			self._proc = proc

	def __getattr__(self, attr):
		if self.remote and attr in self._denied_remote_attrs:
			raise AttributeError(attr)
		return getattr(self._proc, attr)

class ExistingProcess(process.ThreadProcess):
	def __init__(self):
		import threading
		self._lock = threading.Lock()
		super(ExistingProcess, self).__init__(target=lambda x: None, link=None, name='__main__', daemon=False)

	def _receive(self, msg):
		"""the main thread is the only process whose
		receiver pool can be modified by other threads, and therefore
		requires a lock
		"""
		with self._lock:
			super(ExistingProcess, self)._receive(msg)
	
	def wait(self):
		super(ExistingProcess, self).wait()
		self._reset()
	
	def _exit(self):
		super(ExistingProcess, self)._exit()
		process._kill_children(self)

	def _reset(self):
		"""really only makes sense for tests"""
		log.debug("resetting..")
		global _main
		_main = None


