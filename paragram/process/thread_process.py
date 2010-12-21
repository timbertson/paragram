import os
import Queue as queue
import threading
import logging

log = logging.getLogger(__name__)

from base_process import BaseProcess, _send, __EXIT__
from os_process import _process_threads

class ThreadProcess(BaseProcess):
	"""A Thread-backed process"""
	def __init__(self, target, link, **kw):
		daemon = True
		try:
			daemon = kw['daemon']
			del kw['daemon']
		except KeyError:
			pass

		super(ThreadProcess, self).__init__(target, link, **kw)
		self.pid = os.getpid()
		self._private_queue = queue.Queue()
		self._make_queue_feeder()
		self._proc = threading.Thread(target=self._run, name=self.name)
		# add self to the list of threads for this process
		self._register_in_global_thread_list()
		self._proc.daemon=daemon
		self._proc.start()
	
	def _register_in_global_thread_list(self):
		"""
		put self in the global list of thread processes to kill
		if the current process is duplicated
		"""
		_process_threads.put(self)

	
	def _make_queue_feeder(self):
		def feed():
			try:
				while True:
					val = self._queue.get()
					if os.getpid() != self.pid:
						# we've been forked - abort!
						log.warn("feeder thread for duplicate %r got first message - dying" % (self,))
						self._queue.put(val)
						self._die_silently()
						break
					self._private_queue.put(val)
			except (queue.Empty, EOFError): pass

		feeder = threading.Thread(target=feed)
		feeder.daemon = True
		feeder.start()
	
	def _get(self):
		return self._private_queue.get()
	
	def _die_silently(self):
		_send(self._private_queue, __EXIT__)

