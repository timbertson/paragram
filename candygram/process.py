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
__EXIT__ = '__exit__'

# a thread-safe queue is fine here, each spawned process will
# reset its list of _child_process_inputs
_child_process_inputs = queue.Queue()
_process_threads = queue.Queue()

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
		return "<#%s: %s>" % (type(self).__name__, self.name)
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

class ReceiverDecorator(BaseReceiver):
	def __call__(self, *match):
		def _provide_handler(handler):
			self._add_receiver(match, handler)
			return handler
		return _provide_handler

class BaseProcess(ProcessAPI):
	_manager = None
	_next_index = 1
	"""common methods for typical Process implementations"""
	def __init__(self, target, link, name):
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
		log.warn("default _exit_handler called!")
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
			log.debug("%r exiting silently" % (self,))
			pass
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
		log.debug("%s (%s:%s) received message: %r" % (self.name, os.getpid(), type(self).__name__, msg))
		matched = False
		print repr(self._handlers)
		if msg == (__EXIT__,):
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
				matched = True
				break

		if msg == (EXIT,):
			# always exit after the EXIT signal - no more processing allowed
			raise Exit()

		if not matched:
			matched = False
			log.debug("nothing matched!")
			raise UnhandledMessage(msg)
	
	def is_alive(self):
		return self._proc.is_alive()

	def wait(self):
		self._proc.join()
	
	def __reduce__(self):
		"""return an object safe for pickling, in this case
		a proxy object that implements the Process API using only
		this object's queue"""
		return (ProxyProcess, (self.name, self._queue))

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
		log.warn("%s (pid %d) terminating running threads.." % (self, os.getpid()))
		try:
			while True:
				_process_threads.get(False)._die_silently()
				log.warn("got one")
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
		self._private_queue = queue.Queue()
		self._composite_queue = self._make_composite_queue(self._queue, self._private_queue)
		self._proc = threading.Thread(target=self._run, args=(target,), name=self.name)
		# add self to the list of threads for this process
		_process_threads.put(self)
		self._proc.daemon=daemon
		self._proc.start()
	
	def _make_composite_queue(self, a, b):
		"""
		we make a composite queue for the thread's input handling, but
		only ONE of them (self._queue) is exported to other processes.
		This allows us to send messages to only instances of this thread
		in the current process, which is unfortunately necessary to kill
		the damn thing when we start another process!
		"""
		comp = queue.Queue()
		def feed(q):
			try:
				while True:
					val = q.get()
					log.debug("FEEDING: %r" % (pickle.loads(val),))
					comp.put(val)
					if pickle.loads(val) == (__EXIT__,):
						break
			except queue.Empty: pass

		a_thread = threading.Thread(target=feed, args=(a,))
		b_thread = threading.Thread(target=feed, args=(a,))
		a_thread.daemon = b_thread.daemon = True
		a_thread.start()
		b_thread.start()
		return comp
	
	def _get(self):
		return self._composite_queue.get()
	
	def _die_silently(self):
		log.debug("%r, die_silently" % (self,))
		self._private_queue.put(pickle.dumps(__EXIT__))


class ProxyProcess(ProcessAPI):
	def __init__(self, name, queue):
		self.name = name
		self._queue = queue

def _kill_children(self):
	log.warn("%s (pid %d) terminating child processes.." % (self, os.getpid()))
	try:
		while True:
			_child_process_inputs.get(False).put(pickle.dumps(EXIT))
	except queue.Empty:
		pass

default_type = OSProcess
