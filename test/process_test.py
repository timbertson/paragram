from unittest import TestCase
import multiprocessing
from Queue import Empty
import candygram as cg

output = None
main = None

def chain(*fns):
	def chained_func(*a, **kw):
		for fn in fns:
			fn(*a, **kw)
	return chained_func

def ponger(proc):
	"""a process that does what you think it does"""
	proc.receive['ping', cg.Process] = log_and(lambda msg, sender: sender.send('pong', proc))

def log_message(*a):
	output.put(tuple(map(str, a)))

def exit(*a):
	raise cg.process.Exit

log_and_exit = chain(log_message, exit)
def log_and(action):
	return chain(log_message, action)

def dying_proc(proc):
	"""a process that dies when told to do so"""
	proc.receive['die'] = log_and_exit

def spawner(link_to_spawned, on_exit=None):
	"""
	generate a "spawner" function that will respond to
	the 'spawn' method by spawning a new process and
	sending a 'spawned' message back to the sender
	"""
	def _spawner(proc):
		@proc.receiver('spawn', cg.Process)
		def spawn(msg, sender):
			log_message(msg, sender)
			spawnfn = proc.spawnLink if link_to_spawned else proc.spawn
			new_proc = spawnfn(dying_proc, name="dying_proc")
			sender.send('spawned', new_proc)
		if on_exit:
			proc.receive[cg.EXIT, cg.Process] = on_exit
	return _spawner






class ProcessTest(TestCase):
	def setUp(self):
		"""Set up the output event queue"""
		global output, main
		output = multiprocessing.Queue()
		main = cg.main
	
	def tearDown(self):
		"""make sure the main process finishes between runs"""
		cg.main.terminate()
		cg.main.wait()

	@property
	def events(self):
		events = []
		try:
			while True:
				event = output.get(True, 0.2)
				print " >> " + repr(event)
				events.append(event)
		except Empty: pass
		return events

	def test_should_spawn_a_link(self):
		proc = main.spawnLink(ponger, name='ponger')
		def end(message, sender):
			output.put((message, sender.name))
			proc.terminate()

		main.receive['pong', cg.Process] = end
		main.receive['EXIT', cg.Process] = log_and_exit
		proc.send('ping', main)
		main.wait()

		self.assertEquals(self.events, [
			('ping', '__main__'),
			('pong', 'ponger'),
			('EXIT', 'ponger'),
		])

	def test_should_die_on_unknown_message(self):
		proc = main.spawn(ponger, name='ponger')
		proc.send('unknown')
		proc.wait(1)
		self.assertFalse(proc.is_alive())

	def test_should_send_exit_to_linked_process(self):
		self.kill_on_spawned()
		first = main.spawn(spawner(link_to_spawned=True, on_exit=log_and_exit), 'first_proc')
		first.send('spawn', main)
		first.wait()

		self.assertEquals(self.events, [
			('spawn', '__main__'),
			('spawned', 'dying_proc'),
			('die',),
			# we send 'die' to dying_proc, and it sends EXIT to first_proc
			('EXIT', 'dying_proc'),
		])
	
	def test_default_exit_handler_should_exit(self):
		self.kill_on_spawned()
		first = main.spawn(spawner(link_to_spawned=True), 'first_proc')
		first.send('spawn', main)
		first.wait()
		self.assertFalse(first.is_alive())

		self.assertEquals(self.events, [
			('spawn', '__main__'),
			('spawned', 'dying_proc'),
			('die',),
		])

	
	def test_killing_main_should_kill__all__processes(self):
		def monitor_exit(proc):
			proc.receive[cg.EXIT] = log_message
		
		one = main.spawn(monitor_exit, 'one')
		two = main.spawn(monitor_exit, 'two')
		main.terminate()
		one.wait(1)
		two.wait(1)
		self.assertFalse(one.is_alive())
		self.assertFalse(two.is_alive())

		# expect one exit message for each child
		self.assertEquals(self.events, [
			(cg.EXIT,),
			(cg.EXIT,),
		])


	def test_should_not_send_exit_message_to_non_linked_processes(self):
		self.kill_on_spawned()
		first = main.spawn(spawner(link_to_spawned=False, on_exit=log_and_exit), 'first_proc')
		first.send('spawn', main)
		first.wait(0.5)
		# first should still be alive!
		self.assertTrue(first.is_alive())

		# okay, now get rid of it
		first.terminate()
		first.wait()

		self.assertEquals(self.events, [
			('spawn', '__main__'),
			('spawned', 'dying_proc'),
			('die',),
		])
	
	def test_death_of_linked_process_should_be_recoverable(self):
		self.kill_on_spawned()
		first = main.spawn(spawner(link_to_spawned=True, on_exit=log_message), 'first_proc')
		first.send('spawn', main)
		first.wait(1)
		# first should still be alive!
		self.assertTrue(first.is_alive())

		# okay, now get rid of it
		first.terminate()
		first.wait()

		self.assertEquals(self.events, [
			('spawn', '__main__'),
			('spawned', 'dying_proc'),
			('die',),
			(cg.EXIT, 'dying_proc'),
		])


	def test_only_root_process_can_add_receive_to_main(self):
		def first_proc(proc):
			@proc.receiver('go')
			def go(msg):
				try:
					cg.main.receive['foo'] = lambda x: None
				except RuntimeError, e:
					log_message(type(e).__name__)
				proc.terminate()

		first = main.spawn(first_proc, 'first_proc')
		first.send('go')
		first.wait()

		self.assertEquals(self.events, [
			('NotMainProcessError',),
		])
	
	def kill_on_spawned(self):
		main.receive['spawned', cg.Process] = log_and(lambda msg, new_proc: new_proc.send('die'))

