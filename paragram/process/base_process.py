#TODO: all uses of pickle in this module should be completely unnecessary...
import pickle

import os
import multiprocessing
import logging
import sys
import traceback

from paragram import pattern
from paragram.receiver import Receiver
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
	"""
	When this exception is raised, it has the same effect
	as calling :func:`~Process.terminate` on the running
	process.

	:member error: The exception that causes this process to exit.
		This is ``None`` in the case of a call to ``terminate()``
	"""
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
	"""
	The base class of all paragram Process objects.

	:member: error

		If a process terminates with an error, this attribute is set to the exception instance.
		In all other cases, it is ``None``
	"""
	def terminate(self, error=None):
		"""Send an exit message to this process"""
		raise NotImplementedError(type(self))

	def send(self, *msg):
		"""
		Send a message to this process
		"""
		raise NotImplementedError(type(self))

	def is_alive(self):
		"""
		Typically, :func:`wait` is a better choice.
		"""
		raise NotImplementedError(type(self))

	def wait(self, timeout=None):
		"""
		Wait for this process to finish
		"""
		raise NotImplementedError(type(self))
	
class LocalProcess(Process):
	"""
	Code running inside a process can use these methods on the process
	object, in addition to the public methods provided by
	:class:`paragram.Process`

	:member: receive

		Used to set a new receiver, with either of two syntaxes:

			>>> process.receive[message] = handler

		or:

			>>> @process.receive(message)
			>>> def handler(...):
			...     # ...
	
		For more information, see :ref:`handling_messages`
	"""

	def spawn(self, target, name=None, link_to=None, kind=None, args=(), kwargs={}):
		"""
		Spawn a new process. ``target`` is called with the newly-created process
		as its first argument, followed by ``args`` and ``kwargs`` (if present).

		``target`` is responsible for setting up any receivers on the process and
		sending any initial messages. After that, the process will run until terminated.

		:param target: The callable that will be used to init this process.
		:param name: Name of this process, for use in logging, etc.
		:param link_to: used by :func:`~paragram.process.base_process.LocalProcess.spawn_link` to link the newly-created process to
			an existing process.
		:param kind: The class of this process. Should be either :class:`~paragram.OSProcess` or
			:class:`~paragram.ThreadProcess`.
		:param args: extra arguments to pass to ``target``
		:param kwargs: extra keyword arguments to pass to ``target``
		
		"""
		raise NotImplementedError

	def spawn_link():
		"""
		This function calls :func:`~paragram.process.base_process.LocalProcess.spawn` with all provided arguments, setting ``link_to`` to ``self``.
		"""
		raise NotImplementedError


class ProcessAPI(Process):
	"""Default implementation of all public methods for all Process implementations"""
	def terminate(self, error=None):
		self.send(Exit(error))

	def send(self, *msg):
		log.debug("sending msg: %s to process %s" % (msg, self))
		#if len(msg) == 1 and isinstance(msg[0], Exit) and str(self) == '__main__':
		#	raise RuntimeError("bads")
		_send(self._queue, *msg)

	def is_alive(self):
		return not self._finished.is_set()

	def wait(self, timeout=None):
		self._finished.wait(timeout)
	
	@property
	def error(self):
		return pickle.loads(self._error_dict.get('error', None))
	
	def __repr__(self):
		return "<#%s: %s [%s]>" % (self.kind.__name__, self.name, self.pid)
	def __str__(self):
		return self.name
	def __eq__(self, other):
		if not isinstance(other, Process): return False
		return (self.pid, self.index) == (other.pid, other.index)
	def __ne__(self, other): return not self.__eq__(other)

class BaseProcess(ProcessAPI):
	_manager = None
	_next_index = 1
	"""common methods for local Process implementations"""
	def __init__(self, target, link, name, args, kwargs):
		self.kind = type(self)
		self.pid = os.getpid()
		self.name = name
		if not self.name:
			self.name = "%s-%s" % (type(self).__name__, BaseProcess._next_index)
		self._index = BaseProcess._next_index
		BaseProcess._next_index += 1
		self._linked = []
		self._handlers = []
		if link is not None:
			self._linked.append(link)
		self._queue = self._get_manager().Queue()
		self._error_dict = self._get_manager().dict({'error':None})
		self._exit_filter = pattern.gen_filter((Exit,))
		self.receive = Receiver(self._handlers)
		self._init_default_handlers()
		self._target = target
		self._args = args
		self._kwargs = kwargs
		self._finished = self._get_manager().Event()
	
	def _init_default_handlers(self):
		self._default_handlers = [
			(pattern.gen_filter((Exit, Process)), self._exit_handler)
		]

	def _get_manager(self):
		if BaseProcess._manager is None:
			from paragram.managers import ParagramManager
			BaseProcess._manager = ParagramManager()
			BaseProcess._manager.start()
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
				try:
					obj = pickle.loads(pickled)
				except StandardError:
					logging.fatal("Couldn't unpickle data: %r" % (pickled,))
					raise
				self._receive(obj)
		except SilentExit:
			log.debug("duplicate %r exiting silently" % (self,))
		except Exit, e:
			log.info("%s EXIT: %r" % (self, e,))
			self._exit(e.error)
		except KeyboardInterrupt, e:
			self._exit(e)
		except UnhandledMessage, e:
			log.warn(e)
			self._exit(e)
		except Exception, e:
			traceback.print_exc(file=sys.stderr)
			self._exit(e)

	def _exit(self, cause):
		try:
			self._error_dict['error'] = pickle.dumps(cause)
			for linked in self._linked:
				log.info("%s: terminating linked process %s" % (self, linked.name))
				linked.send(Exit(cause), self)
			log.info("process %s ending" % (self.name,))
		finally:
			self._finished.set()

	def _receive(self, msg):
		log.debug("%r received message: %r" % (self, msg))
		matched = False
		if msg == __EXIT__:
			raise SilentExit()

		for filter, handler in self._handlers + self._default_handlers:
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
					traceback.print_exc(file=sys.stderr)
					raise Exit(e)
				break

		if self._exit_filter(msg):
			# always exit after the EXIT signal - no more processing allowed
			raise msg[0]

		if not matched:
			log.debug("process %s had an unhandled message: %r" % (self, msg))
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
		return (ProxyProcess, (self.name, type(self), self._index, self._queue, self.pid, self._error_dict, self._finished))

class SilentExit(Exception): pass

class UnhandledMessage(RuntimeError):
	def __str__(self):
		return "Unhandled message: %r" % (self.args[0],)

class ProxyProcess(ProcessAPI):
	def __init__(self, name, kind, index, queue, pid, error_dict, finished):
		self.name = name
		self._queue = queue
		self.pid = pid
		self.kind = kind
		self._index = index
		self._error_dict = error_dict
		self._finished = finished

