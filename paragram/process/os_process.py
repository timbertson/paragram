import multiprocessing
import Queue as queue
import os
import logging

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

from base_process import BaseProcess, _send, Exit

# a thread-safe queue is fine here, each spawned process will
# reset its list of _child_process_inputs
_child_process_inputs = queue.Queue()
_process_threads = queue.Queue()
class OSProcess(BaseProcess):
	"""an OS-backed process"""
	def __init__(self, target, link, **kw):
		super(OSProcess, self).__init__(target, link, **kw)
		# add our queue to the parent's list of children before we fork()
		_child_process_inputs.put(self._queue)
		self._proc = multiprocessing.Process(target=self._run, name=self.name)
		self._proc.start()
	
	def _run(self, *a):
		self._init_new_process()
		super(OSProcess, self)._run(*a)
	
	def _kill_existing_threads(self):
		global _process_threads
		log.debug("%s (pid %d) terminating newly-duplicated threads.." % (self, os.getpid()))
		try:
			while True:
				_process_threads.get(False)._die_silently()
		except queue.Empty: pass
		_process_threads = queue.Queue()

	def _init_new_process(self):
		import main
		main.main = None
		main._main = None
		# this is a brand new process - so we must not have any children yet
		global _child_process_inputs
		_child_process_inputs = queue.Queue()
		self._kill_existing_threads()
	
	def _exit(self, cause):
		super(OSProcess, self)._exit(cause)
		_kill_children(self, cause)


def _kill_children(self, cause):
	log.debug("%s (pid %d) terminating child processes for cause %r" % (self, os.getpid(), cause))
	try:
		while True:
			q = _child_process_inputs.get(False)
			log.warn( repr(cause))
			_send(q, Exit(cause))
	except queue.Empty:
		log.debug("done killing")
		pass

