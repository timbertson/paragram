"""Tests that patterns in documentation work as advertised"""

import unittest

import paragram as pg
from paragram.pattern import gen_filter

class Pattern(object):
	def __init__(self, match):
		self.matches = gen_filter(match)

class TestPatterns(unittest.TestCase):
	def testAny(self):
		p = Pattern(pg.Any)
		self.assertTrue(p.matches('text'))
		self.assertTrue(p.matches(13.7))
		self.assertTrue(p.matches((1, '', lambda: True)))

	def testShark(self):
		p = Pattern('land shark')
		self.assertTrue(p.matches('land shark'))
		self.assertFalse(p.matches('dolphin'))
		self.assertFalse(p.matches(42))
		self.assertFalse(p.matches([]))

	def test13_7(self):
		p = Pattern(13.7)
		self.assertTrue(p.matches(13.7))
		self.assertFalse(p.matches('text'))
		self.assertFalse(p.matches(13.6))
		self.assertFalse(p.matches({'A': 14}))

	def testInt(self):
		p = Pattern(int)
		self.assertTrue(p.matches(13))
		self.assertTrue(p.matches(42))
		self.assertTrue(p.matches(0))
		self.assertFalse(p.matches('text'))
		self.assertFalse(p.matches(13.7))
		self.assertFalse(p.matches([]))

	def testStr(self):
		p = Pattern(str)
		self.assertTrue(p.matches('plumber'))
		self.assertTrue(p.matches(''))
		self.assertFalse(p.matches(42))
		self.assertFalse(p.matches(0.9))
		self.assertFalse(p.matches(lambda: True))

	def testLambda(self):
		p = Pattern(lambda x: x > 20)
		self.assertTrue(p.matches(42))
		self.assertTrue(p.matches(100))
		self.assertTrue(p.matches(67.7))
		self.assertFalse(p.matches(13))
		self.assertFalse(p.matches(0))
		self.assertFalse(p.matches(-67.7))

	def testTuple(self):
		p = Pattern((str, int))
		self.assertTrue(p.matches(('shark', 42)))
		self.assertTrue(p.matches(('dolphin', 0)))
		self.assertFalse(p.matches(['shark', 42]))
		self.assertFalse(p.matches(('dolphin', 42, 0)))

	def testTuple2(self):
		p = Pattern((str, 20, lambda x: x < 0))
		self.assertTrue(p.matches(('shark', 20, -54.76)))
		self.assertTrue(p.matches(('dolphin', 20, -1)))
		self.assertFalse(p.matches(('shark', 21, -6)))
		self.assertFalse(p.matches((20, 20, -1)))
		self.assertFalse(p.matches(('', 20)))

	def testList(self):
		p = Pattern(['A', str, str])
		self.assertTrue(p.matches(['A', 'B', 'C']))
		self.assertFalse(p.matches(['A', 'B']))
		self.assertFalse(p.matches(['C', 'B', 'A']))
		self.assertFalse(p.matches(['A']))

	def testList2(self):
		p = Pattern([str, int])
		self.assertTrue(p.matches(['dolphin', 42]))
		self.assertFalse(p.matches(['shark']))
		self.assertFalse(p.matches([42, 0]))
		self.assertFalse(p.matches(['dolphin', 42, 'shark']))

	def testList3(self):
		p = Pattern([pg.etc])
		self.assertTrue(p.matches(['dolphin', 42, 0.9]))
		self.assertTrue(p.matches([]))
		self.assertFalse(p.matches(('dolphin', 42, 0.9)))
		self.assertFalse(p.matches('shark'))

	def testDict(self):
		p = Pattern({'S': int, 19: str})
		self.assertTrue(p.matches({'S': 3, 19: 'foo'}))
		self.assertTrue(p.matches({'S': -65, 19: 'bar', 'T': 'me'}))
		self.assertFalse(p.matches({'S': 'Charlie', 19: 'foo'}))
		self.assertFalse(p.matches({'S': 3}))
	
	def testAnyMore(self):
		p = Pattern((1,2, pg.etc))
		self.assertTrue(p.matches((1,2)))
		self.assertTrue(p.matches((1,2,3)))
		self.assertTrue(p.matches((1,2,3, 4, 5, 6, 7)))
		self.assertTrue(p.matches((1,2,3, 4, 'not a number...')))
		self.assertFalse(p.matches((1,3)))
		self.assertFalse(p.matches((1, 1,2)))
