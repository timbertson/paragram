from multiprocessing import managers
import Queue

from process.base_process import Exit, _send

# a subclass purely for the sake of isinstance() checks
class ParagramQueue(Queue.Queue): pass

class ParagramServer(managers.Server):
	def serve_forever(self):
		'''
		Run the server forever
		Copied from the stdlib multiprocessing/managers.py,
		and added extra handling for sending Exit() everywhere
		it can when a keyboardInterrupt is encountered
		'''
		from multiprocessing import current_process
		import threading
		current_process()._manager_server = self
		try:
			while 1:
				try:
					try:
						c = self.listener.accept()
					except (OSError, IOError):
						continue
					t = threading.Thread(target=self.handle_request, args=(c,))
					t.daemon = True
					t.start()
				except KeyboardInterrupt, e:
					# send Exit() to all ParagramQueues we're managing
					for item in self.id_to_obj.values():
						queue = item[0]
						if isinstance(queue, ParagramQueue):
							_send(queue, Exit(e))
					continue
		except SystemExit:
			pass
		finally:
			self.stop = 999
			self.listener.close()


# a sync manager that overrides the Queue type and the get_server() method
# (to use our custom server class)
class ParagramManager(managers.SyncManager):
	def get_server(self):
		'''
		Return server object with serve_forever() method and address attribute
		'''
		from multiprocessing.managers import State
		assert self._state.value == State.INITIAL
		return ParagramServer(self._registry, self._address,
					  self._authkey, self._serializer)
ParagramManager.register('Queue', ParagramQueue)
ParagramManager._Server = ParagramServer
