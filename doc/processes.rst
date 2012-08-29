Processes
=========

(Note: "Process" here refers to the paragram process model - this is *not*
necessarily the same thing that your OS calls a "Process")

A process in paragram is a unit of concurrency, just like erlang.

Processes have a mailbox, and they can send messages to other processes.
Processes should not share state, although this is not prohibited.
The basic lifecycle of a process is:

 - get next message (or wait until a message is received)
 - handle message
 - repeat

This means that while handling a message, a process cannot be *interrupted*, so
a process need not protect its internals with a lock or any other thread-safety
measures.

It also means that messages should not be considered to be immediate - they can be
queued for an arbitrary amount of time, depending on how busy the receiving
process is. Because of this, you should make sure that your process never blocks
indefinitely - if you do, messages will *never* be delivered, including termination
messages - and then your app won't shut down.

As an implementation detail, a paragram process can either be implemented as a
python thread or as a separate OS process. You should use threads where possible,
as they are much more efficient. You may prefer to use processes in the following cases:

 - you need concurrency across multiple cores, and python's `GIL`_ prevents that
 - you need to protect the current process from state modification
   by subprocesses. `autonose`_ does this to ensure that imported modules
   are not cached between test runs.

You can specify what kind of process should be created by passing the ``kind``
keyword argument to either :func:`spawn` or :func:`~paragram.process.base_process.ProcessAPI.spawn_link`.

.. note::
  OS-based processes may not work on windows, as paragram relies on the
  ``multiprocessing`` library to create new processes.

Spawning new processes
----------------------

Any existing process can spawn a new process. When creating
the first process, you can use :data:`paragram.main`.
Here's a simple quickstart that shows how you can start a process
and send it a message, and how the process handles a message.

	>>> import paragram as pg
	>>> import time
	>>> def init_process(proc):
	...     print "process started!"
	...     @proc.receive("go away")
	...     def go_away(msg):
	...         print "process ending."
	...         proc.terminate()
	...
	>>> proc = pg.main.spawn_link(target=init_process, name="my first process"); time.sleep(0.5)
	process started!
	>>> proc.send("go away")
	>>> proc.wait()
	process ending.

You should spawn processes using :func:`~paragram.process.ProcessAPI.spawn_link`. This
creates a _linked_ process. If you want to create an unlinked process, you can use
:func:`~paragram.process.ProcessAPI.spawn`. See :ref:`terminating` for more details.

.. _handling_messages:

Handling Messages
-----------------

Messages in erlang are handled via pattern matching. Python doesn't have
pattern matching as part of the language, but we can do a decent job for most cases.

Messages can be matched on by equality or by type. For example:

	>>> proc.receiver["hello"] = some_func

Will cause some_func to handle any message that is ``("hello",)``.

	>>> proc.receiver[str, int] = some_func

Will match any message that consists of a string and an integer. For example, ``("hello", 1)``
or ``("two", 2)``.

For the full documentation of pattern matching, see :doc:`pattern-matching`.


When a receiver's pattern matches, it is called with the arguments of
the message. For example, when the message ``("hello", 123)`` is
matched, the associated function gets both arguments, so it
should have the following signature:

  >>> def handle(msg, num):
  ...     # ...

There is no support for keyword arguments in messages.

When setting up a process' receivers, you have two
syntaxes available:

	>>> proc.receive[pattern] = callable

and:

	>>> @proc.receive(pattern)
	... def callable(\*args):
	...     # ...

The first syntax is mostly useful for (re)using an existing
callable.

But if the receiver is only going to be used once,
it can be convenient to define it inline, as in
the second example.


.. _terminating:

Terminating
-----------

At any point, you can call :func:`~paragram.process.ProcessAPI.terminate` on a process
to send it an exit message.

While inside a message handler, you can also raise :exc:`paragram.Exit` if you don't
have a reference to the current procss - it will have the same effect.

At any point, if a process receives a message that matches no receivers, it will
terminate with an UnhandledMessage exception.

When a process terminates, it sends a message of the form ``(exit, process)``
to each of its linked processes.

By default, a process receiving such a message will itself terminate. But you can
override that behaviour like so:

	>>> import paragram as pg
	>>> @proc.receive(pg.Exit, pg.Process)
	>>> def linked_terminated(exit, proc):
	...     pass # handle however you like

Note that the ``exit`` paramater here is of type :class:`paragram.Exit`, and so has
a ``error`` attribute. This is set to the exception instance in the case of a failure,
or ``None`` when a process is terminated normally via :func:`~paragram.process.ProcessAPI.terminate`

If you *don't* want to be informed when a process terminates, you should use
:func:`~paragram.process.ProcessAPI.spawn` instead of :func:`~paragram.process.ProcessAPI.spawn_link`.


.. _gil: http://en.wikipedia.org/wiki/Global_Interpreter_Lock
.. _autonose: https://github.com/gfxmonk/autonose/
