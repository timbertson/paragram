from process.main import main
from process.base_process import BaseProcess
from process import Process, ThreadProcess

graph_enabled = False

def graph(filename="paragram.dot"):
	"""
	Create a dotfile of the current set of linked processes (starting from __main__)
	"""
	import itertools
	if not graph_enabled:
		raise RuntimeError("Graphs are not enabled. make sure you call enable_graphs *before* spawning any processes")
	def grapher(proc):
		done = []
		links = []
		@proc.receive(__GRAPH__, Process, list)
		def graph_proc(msg, sender, linked):
			if done:
				raise RuntimeError("graphing already complete - got late message from %r" % (sender,))
			links.append((sender, linked))

		@proc.receive('done')
		def complete(*a):
			done.append(True)
			with open(filename, 'w') as output:
				print >> output, "digraph paragram_state {"
				for source, dests in links:
					print >> output, '"%r" [label="%s"];' % (source, source)
					for dest in dests:
						print >> output, '"%r" -> "%r";' % (source, dest)
				procs = [l[0] for l in links]
				get_pid = lambda x: x.pid
				pid_groups = itertools.groupby(sorted(procs, key=get_pid), get_pid)
				for pid, members in pid_groups:
					print >> output, "subgraph cluster_%s {" % (pid,)
					print >> output, 'label = "PID %s";' % (pid,)
					print >> output, "color=black;"
					print >> output, ";\n".join(['"%r"' % (member,) for member in members])
					print >> output, "}"
				print >> output, "}"
			proc.terminate()

	grapher_proc = main.spawn(grapher, name="graph collector", kind=ThreadProcess)
	main.send(__GRAPH__, grapher_proc)
	print "waiting for graph input..."
	import time
	time.sleep(1)
	grapher_proc.send('done')
	grapher_proc.wait()
	if grapher_proc.error:
		raise grapher_proc.error

__GRAPH__ = '__GRAPH__'
def enable_graphs():
	"""
	monkey-patch BaseProcess to allow for graph information collecting.
	This must be called before graph()
	"""
	global graph_enabled
	graph_enabled = True
	init_default_handlers_without_graphing = BaseProcess._init_default_handlers
	def init_default_handlers_with_graphing(self):
		init_default_handlers_without_graphing(self)
		self.receive[__GRAPH__, Process] = self._graph_links

	def _graph_links(self, msg, collector):
		if getattr(self, '_graphing', False):
			return
		self._graphing = True
		collector.send(__GRAPH__, self, self._linked)
		for linked in self._linked:
			linked.send(__GRAPH__, collector)

	BaseProcess._graph_links = _graph_links
	BaseProcess._init_default_handlers = init_default_handlers_with_graphing
