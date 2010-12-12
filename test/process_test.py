from unittest import TestCase
import multiprocessing
from Queue import Empty
import time
import candygram as cg

output = None
main = None
import logging

def chain(*fns):
	def chained_func(*a, **kw):
		for fn in fns:
			fn(*a, **kw)
	return chained_func

class Ponger(object):
	def __init__(self, proc):
		logging.warn("started")
		self.proc = proc
		self.proc.receive['ping', cg.Process] = self.ping
		self.proc.receive['go away'] = self.exit_gracefully
		self.proc.receive['die horribly'] = self.die
	
	def ping(self, message, sender):
		output.put((message, sender.name))
		sender.send('pong', self.proc)
	
	def exit_gracefully(self):
		self.proc.exit()
	
	def die(self):
		import sys
		sys.exit(1)

class ProcessTest(TestCase):
	def setUp(self):
		global output, main
		output = multiprocessing.Queue()
		main = cg.main
	
	def tearDown(self):
		cg.main.terminate()
		cg.main.wait()
	
	@property
	def events(self):
		events = []
		try:
			while True:
				event = output.get(True, 1)
				print " >> " + repr(event)
				events.append(event)
		except Empty: pass
		return events

	def log_message(self, *a):
		output.put(tuple(map(str, a)))
	
	def exit(self, *a):
		raise cg.process.Exit

	def test_should_spawn_a_link(self):
		proc = main.spawnLink(Ponger, name='ponger')
		def end(message, sender):
			output.put((message, sender.name))
			proc.terminate()

		main.receive['pong', cg.Process] = end
		main.receive['EXIT', cg.Process] = chain(self.log_message, self.exit)
		proc.send('ping', main)
		main.wait()

		self.assertEquals(self.events, [
			('ping', '__main__'),
			('pong', 'ponger'),
			('EXIT', 'ponger'),
		])

	def test_should_die_on_unknown_message(self):
		proc = main.spawn(Ponger, name='ponger')
		proc.send('unknown')
		proc.wait(1)
		self.assertFalse(proc.is_alive())

	def test_should_send_exit_to_linked_process(self):
		def dying_proc(proc):
			proc.receive['die'] = chain(self.log_message, self.exit)

		def first_proc(proc):
			@proc.receiver('spawn', cg.Process)
			def spawn(msg, main_proc):
				self.log_message(msg, main_proc)
				new_proc = proc.spawnLink(dying_proc, name="dying_proc")
				main_proc.send('spawned', new_proc)
			proc.receive[cg.EXIT, cg.Process] = chain(self.log_message, self.exit)

		import os
		print os.getpid()
		main.receive['spawned', cg.Process] = chain(self.log_message, lambda msg, new_proc: new_proc.send('die'))
		first = main.spawn(first_proc, 'first_proc')
		first.send('spawn', main)
		first.wait()

		self.assertEquals(self.events, [
			('spawn', '__main__'),
			('spawned', 'dying_proc'),
			('die',),
			# we send 'die' to dying_proc, and it sends EXIT to first_proc
			('EXIT', 'dying_proc'),
		])
	
	def test_killing_main_should_kill__all__processes(self):
		pass
	
	def test_main_should_always_point_to_the_root_process(self):
		pass
	
	def test_death_of_process_should_propagate(self):
		pass

	def test_death_of_process_should_be_catchable(self):
		pass

	def test_only_root_process_can_add_receive_to_main(self):
		pass

#if __name__ == '__main__':
#	filter = cg.pattern.genFilter(('foo', object))
#	assert filter(('foo', object()))
#	p = ProcessTest()
#	ProcessTest.runTest = ProcessTest.test_should_spawn_a_link
#	p.setUp()
#	p.runTest()
#	#p.test_should_spawn_a_link()
