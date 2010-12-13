#TODO: all uses of pickle in this module should be completely unnecessary...
import pickle

import sys
import os
import multiprocessing
import logging

from paragram import pattern
from receiver import ReceiverSetter, ReceiverDecorator
log = logging.getLogger(__name__)

EXIT = 'EXIT'
# an internal message used for killing off duplicated ThreadProcess objects
__EXIT__ = ('__exit_silently__',)

def _send(queue, *msg):
	queue.put(pickle.dumps(msg))

class Process(object):
	"""empty class for the purpose of inheritance"""
	pass

class PreventExit(Exception): pass

class ProcessAPI(Process):
	"""the public methods for all Process implementations"""
	def terminate(self):
		self.send(EXIT)

	def spawn_link(self, *a, **kw):
		kw['link_to'] = self
		return self.spawn(*a, **kw)
	
	def spawn(self, target, name=None, link_to=None, kind=None):
		if kind is None:
			import paragram
			kind=paragram.default_type
		return kind(target=target, link=link_to, name=name)
	
	def send(self, *msg):
		log.debug("sending msg: %s to process %s" % (msg, self))
		self._queue.put(pickle.dumps(msg))

	def __repr__(self):
		return "<#%s: %s [%s]>" % (type(self).__name__, self.name, os.getpid())
	def __str__(self):
		return self.name


class BaseProcess(ProcessAPI):
	_manager = None
	_next_index = 1
	"""common methods for local Process implementations"""
	def __init__(self, target, link, name):
		self.pid = os.getpid()
		self.name = name
		if not self.name:
			self.name = "%s-%s" % (type(self).__name__, BaseProcess._next_index)
			BaseProcess._next_index += 1
		self._linked = []
		self._handlers = []
		if link is not None:
			self._linked.append(link)
		self._queue = self._get_manager().Queue()
		self._exit_filter = pattern.genFilter((EXIT, Process))
		self.receive = ReceiverSetter(self._handlers)
		self.receiver = ReceiverDecorator(self._handlers)
		#self._auto_exit = True
	
	
	def _get_manager(self):
		if BaseProcess._manager is None:
			BaseProcess._manager = multiprocessing.Manager()
		return BaseProcess._manager
	
	def _exit_handler(self, exit, proc=None):
		self.send(EXIT)
	
	def _get(self):
		return self._queue.get()

	def _run(self, target):
		try:
			target(self)
			while True:
				pickled = self._get()
				self._receive(pickle.loads(pickled))
		except SilentExit:
			log.debug("duplicate %r exiting silently" % (self,))
		except Exit:
			self._exit()
		except UnhandledMessage, e:
			log.error(e)
			self._exit()
		except Exception:
			import traceback
			traceback.print_exc(file=sys.stderr)
			self._exit()

	def _exit(self):
		for linked in self._linked:
			log.info("terminating linked process %s" % (linked.name,))
			linked.send(EXIT, self)
		log.info("process %s ending" % (self.name,))

	def _receive(self, msg):
		log.debug("%r received message: %r" % (self, msg))
		matched = False
		if msg == __EXIT__:
			raise SilentExit()
		for filter, handler in self._handlers + [(self._exit_filter, self._exit_handler)]:
			matched = False
			try:
				matched = filter(msg)
			except StandardError: pass
			if matched:
				if isinstance(msg, tuple):
					args = msg
				else:
					args = (msg,)
				handler(*args)
				break

		if msg == (EXIT,):
			# always exit after the EXIT signal - no more processing allowed
			raise Exit()

		if not matched:
			raise UnhandledMessage(msg)
	
	def is_alive(self):
		return self._proc.is_alive()

	def wait(self, timeout=None):
		self._proc.join(timeout)
	
	def __reduce__(self):
		"""return an object safe for pickling, in this case
		a proxy object that implements the Process API using only
		this object's queue"""
		return (ProxyProcess, (self.name, self._queue, self.pid))

class SilentExit(Exception): pass
class Exit(RuntimeError):
	def __init__(self, cause=None):
		self.cause = cause

class UnhandledMessage(RuntimeError):
	def __str__(self):
		return "Unhandled message: %r" % (self.args[0],)

class ProxyProcess(ProcessAPI):
	def __init__(self, name, queue, pid):
		self.name = name
		self._queue = queue
		self.pid = pid

