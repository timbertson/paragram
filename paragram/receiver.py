from paragram import pattern
class Receiver(object):
	def __init__(self, handlers):
		self._handlers = handlers

	def _add_receiver(self, match, handler):
		assert handler is not None
		self._handlers.append((pattern.gen_filter(match), handler))

	def __setitem__(self, match, handler):
		if not isinstance(match, tuple):
			match = (match,)
		self._add_receiver(match, handler)

	def __call__(self, *match):
		def _provide_handler(handler):
			self._add_receiver(match, handler)
			return handler
		return _provide_handler

