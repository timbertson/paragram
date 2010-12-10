from unittest import TestCase
import multiprocessing
from Queue import Empty
import candygram as cg
import time

output = None
main = None
import logging

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
		cg.main._auto_exit = False
	
	def tearDown(self):
		time.sleep(0.2)
	
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

	def log_message(self, message, caused_by):
		output.put((message, caused_by.name))

	def test_should_spawn_a_link(self):
		proc = main.spawnLink(Ponger, name='ponger')
		def end(message, sender):
			output.put((message, sender.name))
			proc.terminate()

		main.receive['pong', cg.Process] = end
		main.receive['EXIT', cg.Process] = self.log_message
		proc.send('ping', main)

		self.assertEquals(self.events, [
			('ping', '__main__'),
			('pong', 'ponger'),
			('EXIT', 'ponger'),
		])

	def test_should_die_on_unknown_message(self):
		proc = main.spawnLink(Ponger, name='ponger')
		proc.send('unknown')

		self.assertEquals(self.events, [
			('ping', '__main__'),
			('pong', 'ponger'),
			('EXIT', 'ponger'),
		])

	def test_should_ignore_standard_errors_in_filter_matching(self):
		pass

	def test_should_send_exit_to_linked_process(self):
		pass
	
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
