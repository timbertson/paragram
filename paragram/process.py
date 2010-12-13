#TODO: all uses of pickle in this module should be completely unnecessary...
import pickle

import sys
import os
import multiprocessing
import threading
import Queue as queue
import pattern
import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

EXIT = 'EXIT'
# an internal message used for killing off duplicated ThreadProcess objects
__EXIT__ = ('__exit_silently__',)

# a thread-safe queue is fine here, each spawned process will
# reset its list of _child_process_inputs
_child_process_inputs = queue.Queue()
_process_threads = queue.Queue()

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

	def spawnLink(self, *a, **kw):
		kw['link_to'] = self
		return self.spawn(*a, **kw)
	
	def spawn(self, target, name=None, link_to=None, kind=None):
		if kind is None:
			kind=default_type
		return kind(target=target, link=link_to, name=name)
	
	def send(self, *msg):
		log.debug("sending msg: %s to process %s" % (msg, self))
		self._queue.put(pickle.dumps(msg))

	def __repr__(self):
		return "<#%s: %s [%s]>" % (type(self).__name__, self.name, os.getpid())
	def __str__(self):
		return self.name


class BaseReceiver(object):
	def __init__(self, handlers):
		self._handlers = handlers
	
	def _add_receiver(self, match, handler):
		assert handler is not None
		self._handlers.append((pattern.genFilter(match), handler))
	
class ReceiverSetter(BaseReceiver):
	__setitem__ = BaseReceiver._add_receiver
	def __setitem__(self, match, handler):
		if not isinstance(match, tuple):
			match = (match,)
		self._add_receiver(match, handler)

class ReceiverDecorator(BaseReceiver):
	def __call__(self, *match):
		def _provide_handler(handler):
			self._add_receiver(match, handler)
			return handler
		return _provide_handler

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

class OSProcess(BaseProcess):
	"""an OS-backed process"""
	def __init__(self, target, link, **kw):
		super(OSProcess, self).__init__(target, link, **kw)
		# add our queue to the parent's list of children before we fork()
		_child_process_inputs.put(self._queue)
		self._proc = multiprocessing.Process(target=self._run, args=(target,), name=self.name)
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
	
	def _exit(self):
		super(OSProcess, self)._exit()
		_kill_children(self)

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
		self._proc = threading.Thread(target=self._run, args=(target,), name=self.name)
		# add self to the list of threads for this process
		_process_threads.put(self)
		self._proc.daemon=daemon
		self._proc.start()
	
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

class ProxyProcess(ProcessAPI):
	def __init__(self, name, queue, pid):
		self.name = name
		self._queue = queue
		self.pid = pid

def _kill_children(self):
	log.debug("%s (pid %d) terminating child processes.." % (self, os.getpid()))
	try:
		while True:
			q = _child_process_inputs.get(False)
			_send(q, EXIT)
	except queue.Empty:
		pass

default_type = OSProcess
