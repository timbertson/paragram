# pattern.py
#
# Copyright (c) 2004 Michael Hobbs,
# modifications by Tim Cuthbertson
#
# This file was originally distributed as part of Candygram.
#
# Candygram is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# Candygram is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Candygram; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import types


# Generate a unique value for 'Any' so that it won't ever be confused with any
# other value.
Any = object()
etc = object()

def gen_filter(pattern):
	"""generate a pattern filter"""
	if isinstance(pattern, tuple) or isinstance(pattern, list):
		result = seq_filter(pattern)
	elif isinstance(pattern, dict):
		result = dict_filter(pattern)
	elif isinstance(pattern, type) or type(pattern) is types.ClassType:
		result = type_filter(pattern)
	elif callable(pattern):
		result = pattern
	elif pattern is Any:
		result = any_filter
	else:
		result = value_filter(pattern)
	return result

def any_filter(x): return True

def value_filter(value):
	def value_equals(x): return x == value
	return value_equals

def type_filter(t):
	def instance_of(x): return isinstance(x, t)
	return instance_of

def seq_filter(seq):
	"""gen filter for a sequence pattern"""
	# Define these values as constants outside of the filt() function so that
	# the filter will not have to re-calculate the values every time it's called.
	allowLonger = False
	if etc in seq:
		# etc must come last
		assert etc not in seq[:-1]
		seq = seq[:-1]
		allowLonger = True
	seqLen = len(seq)
	subFilters = map(gen_filter, seq)
	correct_type = type_filter(type(seq))
	def filt(x):
		"""resulting filter function"""
		if not correct_type(x):
			return False
		if len(x) < seqLen:
			return False
		if len(x) > seqLen and not allowLonger:
			return False
		for subfilter, item in zip(subFilters, x):
			if not subfilter(item):
				return False
		return True
	return filt


def dict_filter(dict_):
	"""gen filter for a dictionary pattern"""
	subFilters = []
	for key, pattern in dict_.items():
		subFilters.append((key, gen_filter(pattern)))
	def filt(x):
		"""resulting filter function"""
		for key, subFilter in subFilters:
			if key not in x:
				return False
			if not subFilter(x[key]):
				return False
			# end if
		return True
	return filt
