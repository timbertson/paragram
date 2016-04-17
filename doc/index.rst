.. image:: http://gfxmonk.net/dist/status/project/paragram.png

What is paragram?
=================

Paragram is an erlang-style concurrency framework for python. This is also known
as an `actor-based concurrency model <http://en.wikipedia.org/wiki/Actor_model>`_,
as it consists of multiple independent `actors` sending messages to each other.

Paragram started as a fork of `candygram`_
adding true concurrency using threads and processes, but diverged enough to become its
own library.

Documentation Sections:
-----------------------

.. toctree::
   :maxdepth: 2

   processes
   pattern-matching
   api


Performance
===========

Paragram is *not* (currently) performant for large numbers of processes.
It does well enough with threads, but starting more than a handlful of processes
will cause delays when spawning, because of the large number of inter-process objects.
This will hopefully be fixed in the future, but you should be aware of it.

If you need performance, I suggest trying `candygram`_, which features lightweight
tasklets instead of threads or OS processes.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _candygram: http://candygram.sourceforge.net/
