#TODO: all uses of pickle in this module should be completely unnecessary...
import pickle

import sys
import multiprocessing
import threading
import pattern
import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

EXIT = 'EXIT'

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
	
	def spawn(self, target, name, link_to=None, kind=None):
		if kind is None:
			kind=default_type
		return kind(target=target, link=link_to, name=name)
	
	def send(self, *msg):
		log.debug("sending msg: %s to q %s" % (msg, self._queue))
		self._queue.put(pickle.dumps(msg))


class Receiver(object):
	def __init__(self, handlers):
		self._handlers = handlers
	
	def _add_receiver(self, match, handler):
		self._handlers.append((pattern.genFilter(match), handler))
	
	__call__ = _add_receiver
	__setitem__ = _add_receiver

class BaseProcess(ProcessAPI):
	_manager = None
	_next_index = 1
	"""common methods for typical Process implementations"""
	def __init__(self, target, link, name):
		self.name = name
		if not self.name:
			self.name = "%s-%s" % (type(self), BaseProcess._next_index)
			BaseProcess._next_index += 1
		self._linked = []
		self._handlers = []
		if link is not None:
			self._linked.append(link)
		self._queue = self._get_manager().Queue()
		self._exit_filter = pattern.genFilter((EXIT, Process))
		self.receive = Receiver(self._handlers)
		self._auto_exit = True
	
	def _get_manager(self):
		if BaseProcess._manager is None:
			BaseProcess._manager = multiprocessing.Manager()
		return BaseProcess._manager
	
	def _exit_handler(self, exit, proc=None):
		self._exit()

	def _run(self, target):
		try:
			target(self)
			while True:
				pickled = self._queue.get()
				self._receive(pickle.loads(pickled))
		except Exit:
			pass
		except UnhandledMessage, e:
			print >> sys.stderr, str(e)
		except Exception:
			import traceback
			traceback.print_exc(file=sys.stderr)
		finally:
			self._exit()

	def _exit(self):
		for linked in self._linked:
			log.info("terminating linked process %s" % (linked.name,))
			linked.send(EXIT, self)
		log.info("process %s ending" % (self.name,))

	def _receive(self, msg):
		log.debug("%s (%s) received message: %r" % (self.name, type(self), msg))
		matched = False
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
	
	def __reduce__(self):
		"""return an object safe for pickling, in this case
		a proxy object that implements the Process API using only
		this object's queue"""
		return (ProxyProcess, (self.name, self._queue))

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
		self._proc = multiprocessing.Process(target=self._run, args=(target,), name=self.name)
		#self._proc = threading.Thread(target=self._run, args=(target,), name=self.name)
		self._proc.daemon=True #necesasry?
		self._proc.start()
	

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
		self._thread = threading.Thread(target=self._run, args=(target,), name=self.name)
		self._thread.daemon=daemon #necesasry?
		self._thread.start()

class ProxyProcess(ProcessAPI):
	def __init__(self, name, queue):
		self.name = name
		self._queue = queue


default_type = OSProcess
