Pattern Matching
================

Rules
-----

#. If the value is the constant, ``paragram.Any``, then any message will match.
#. If the value is a type object or a class, then any message that isinstance()
   of the type or class will match.
#. If the value is callable(), then a message will match if the function/method
   returns True when called with the message.
#. If the value is a tuple, then a message will match only if it is a tuple of
   the same length (but see next point). Also, each value in the tuple is used
   as a pattern and the tuple as a whole will match only if every sub-pattern in
   the tuple matches its associated value in the message.
#. If the last item in a tuple is the constant ``paragram.etc``, then it will
   match any remaining elements in the tuple, similar to an ``*args``
   specification in a paramater list.
#. If the value is a list, then the same rule for tuples applies.
#. If the value is a dictionary, then a message will match only if it is a
   dictionary that contains all of the same keys as the pattern value. Also,
   each value in the dictionary is used as a pattern and the dictionary as a
   whole will match only if every pattern in the dictionary matches its
   associated value in the message.
#. Any other value is treated as a literal pattern, and matches any object that
   is equal to it.

Note that every message in paragram is a tuple, so in order to match any number
of any objects, you should add a receiver for ``paragram.etc``.

Examples
--------

Let's illustrate these rules by example.

In the table below, the first column contains a Python value that is used as a pattern.
The second column contains Python values that match the pattern and the third column contains Python values that do not match the pattern.

=================================  =============================================================  =====================================================
Pattern                            Matches                                                        Non-Matches
=================================  =============================================================  =====================================================
``Any``                            ``'text'``, ``13.7``, ``(1, '', lambda: true)``
``'land shark'``                   ``'land shark'``                                               ``'dolphin'``, ``42``, ``[]``
``13.7``                           ``13.7``                                                       ``'text'``, ``13.6``, ``{'A': 14}``
``int``                            ``13``, ``42``, ``0``                                          ``'text'``, ``13.7``, ``[]``
``str``                            ``'plumber'``, ``''``                                          ``42``, ``0.9``, ``lambda: True``
``lambda x,y,z: x+y+z == 3``       ``(1, 1, 1)``, ``(3, 1, -1)``                                  ``(3,)``, ``(1, 2, 3)``
``(str, int)``                     ``('shark', 42)``, ``('dolphin', 0)``                          ``['shark', 42]``, ``('dolphin', 42, 0)``
``(str, int, etc)``                ``('shark', 42)``, ``('dolphin', 0, 1, 2, True)``              ``['shark', 42]``, ``('dolphin', 42, 0)``
``(str, 20, lambda x: x < 0)``     ``('shark', 20, -54.76)``, ``('dolphin', 20, -1)``             ``('shark', 21, -6)``, ``(20, 20, -1)``, ``('', 20)``
``['A', str, str]``                ``['a', 'b', 'c', 'd']``, ``['a', 'b']``                       ``['C', 'B', 'A']``, ``['A']``
``[str, int]``                     ``['dolphin', 42, 0]``, ``['shark']``                          ``[42, 0]``, ``['dolphin', 42, 'shark']``
``[Any]``                          ``['dolphin', 42, 0.9]``, ``[]``                               ``('dolphin', 42, 0.9)``, ``'shark'``
``{'S': int, 19: str}``            ``{'S': 3, 19: 'foo'}``, ``{'S': -65, 19: 'bar', 'T': 'me'}``  ``{'S': 'Charlie', 19: 'foo'}``, ``{'S': 3}``
=================================  =============================================================  =====================================================
