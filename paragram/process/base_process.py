#TODO: all uses of pickle in this module should be completely unnecessary...
import pickle

import sys
import os
import multiprocessing
import logging

from paragram import pattern
from receiver import ReceiverSetter, ReceiverDecorator
log = logging.getLogger(__name__)

def can_pickle(o):
	try:
		pickle.dumps(o)
		return True
	except pickle.PicklingError:
		return False

class UnpicklableForeignException(RuntimeError): pass
class UnhandledChildExit(RuntimeError): pass

class Exit(Exception):
	def __init__(self, cause=None):
		while isinstance(cause, Exit):
			cause = cause.error
		super(Exit, self).__init__(cause)
		self.error = cause if can_pickle(cause) else UnpicklableForeignException(repr(cause))

	def __str__(self):
		return 'EXIT'
	def __repr__(self):
		return '<#EXIT: %r>' % (self.error,)
	def __eq__(self, other):
		return type(self) == type(other) and self.error == other.error


#EXIT = 'EXIT'
# an internal message used for killing off duplicated ThreadProcess objects
__EXIT__ = ('__exit_silently__',)

def _send(queue, *msg):
	queue.put(pickle.dumps(msg))

class Process(object):
	"""empty class for the purpose of inheritance"""
	pass

class ProcessAPI(Process):
	"""the public methods for all Process implementations"""
	def terminate(self, error=None):
		self.send(Exit(error))

	def send(self, *msg):
		log.debug("sending msg: %s to process %s" % (msg, self))
		_send(self._queue, *msg)

	def is_alive(self):
		return not self._finished.is_set()

	def wait(self, timeout=None):
		self._finished.wait(timeout)
	
	@property
	def error(self):
		return self._error_dict.get('error', None)
	
	def __repr__(self):
		return "<#%s: %s [%s]>" % (type(self).__name__, self.name, os.getpid())
	def __str__(self):
		return self.name

class BaseProcess(ProcessAPI):
	_manager = None
	_next_index = 1
	"""common methods for local Process implementations"""
	def __init__(self, target, link, name, args, kwargs):
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
		self._error_dict = self._get_manager().dict({'error':None})
		self._child_exit_filter = pattern.genFilter((Exit, Process))
		self._exit_filter = pattern.genFilter((Exit,))
		self.receive = ReceiverSetter(self._handlers)
		self.receiver = ReceiverDecorator(self._handlers)
		self._target = target
		self._args = args
		self._kwargs = kwargs
		self._finished = self._get_manager().Event()
	
	def _get_manager(self):
		if BaseProcess._manager is None:
			BaseProcess._manager = multiprocessing.Manager()
		return BaseProcess._manager
	
	def _exit_handler(self, exit, proc=None):
		self.send(Exit(UnhandledChildExit(proc)))
	
	def _get(self):
		return self._queue.get()

	def _run(self):
		try:
			self._target(self, *self._args, **self._kwargs)
			while True:
				pickled = self._get()
				self._receive(pickle.loads(pickled))
		except SilentExit:
			log.debug("duplicate %r exiting silently" % (self,))
		except Exit, e:
			log.warn("EXIT: %r" % (e,))
			self._exit(e.error)
		except UnhandledMessage, e:
			log.warn(e)
			self._exit(e)
		except Exception, e:
			log.exception("exception encountered in process %s:" % (self,))
			self._exit(e)

	def _exit(self, cause):
		self._error_dict['error'] = cause
		for linked in self._linked:
			log.info("terminating linked process %s" % (linked.name,))
			linked.send(Exit(cause), self)
		log.info("process %s ending" % (self.name,))
		self._finished.set()

	def _receive(self, msg):
		log.debug("%r received message: %r" % (self, msg))
		matched = False
		if msg == __EXIT__:
			raise SilentExit()
		for filter, handler in self._handlers + [(self._child_exit_filter, self._exit_handler)]:
			matched = False
			try:
				matched = filter(msg)
			except StandardError: pass
			if matched:
				if isinstance(msg, tuple):
					args = msg
				else:
					args = (msg,)
				try:
					handler(*args)
				except Exception, e:
					raise Exit(e)
				break

		if self._exit_filter(msg):
			# always exit after the EXIT signal - no more processing allowed
			raise msg[0]

		if not matched:
			#log.debug("unhandled message: %r" % (msg,))
			raise UnhandledMessage(msg)
	
	def spawn_link(self, *a, **kw):
		kw['link_to'] = self
		child = self.spawn(*a, **kw)
		self._linked.append(child)
		return child
	
	def spawn(self, target, name=None, link_to=None, kind=None, args=(), kwargs={}):
		if kind is None:
			import paragram
			kind=paragram.default_type
		child = kind(target=target, link=link_to, name=name, args=args, kwargs=kwargs)
		cls, args = child.__reduce__()
		return cls(*args)
	
	def __reduce__(self):
		"""return an object safe for pickling, in this case
		a proxy object that implements the Process API using only
		this object's queue"""
		return (ProxyProcess, (self.name, self._queue, self.pid, self._error_dict, self._finished))

class SilentExit(Exception): pass

class UnhandledMessage(RuntimeError):
	def __str__(self):
		return "Unhandled message: %r" % (self.args[0],)

class ProxyProcess(ProcessAPI):
	def __init__(self, name, queue, pid, error_dict, finished):
		self.name = name
		self._queue = queue
		self.pid = pid
		self._error_dict = error_dict
		self._finished = finished

