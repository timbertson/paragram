# pattern.py
#
# Copyright (c) 2004 Michael Hobbs
#
# This file is part of Candygram.
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

"""Pattern filter generator"""

__revision__ = '$Id: pattern.py,v 1.9 2004/09/03 17:06:46 hobb0001 Exp $'


import types
import warnings


# Generate a unique value for 'Any' so that it won't ever be confused with any
# other value.
Any = object()
# WARNING! WARNING! WARNING! AnyRemaining has been deprecated. Do not use it.
AnyRemaining = object()


def genFilter(pattern):
	"""generate a pattern filter"""
	if isinstance(pattern, tuple) or isinstance(pattern, list):
		result = genSeqFilter(pattern)
	elif isinstance(pattern, dict):
		result = genDictFilter(pattern)
	elif isinstance(pattern, type) or type(pattern) is types.ClassType:
		result = genTypeFilter(pattern)
	elif callable(pattern):
		result = genFuncFilter(pattern)
	elif pattern is Any:
		result = genAnyFilter()
	elif pattern is AnyRemaining:
		warnings.warn(
				'The candygram.AnyRemaining constant is deprecated. ' \
				'Please use a standard list pattern instead.',
				DeprecationWarning,
				5)  # Usually called from addHandler(genFilter(genSeqFilter(...)))
		result = genAnyFilter()
	else:
		result = genValueFilter(pattern)
	return result


def genAnyFilter():
	"""gen filter for Any"""
	return lambda x: True


def genValueFilter(value):
	"""gen filter for a specific value"""
	return lambda x: x == value


def genFuncFilter(func):
	"""gen filter for a function"""
	return func


def genTypeFilter(t):
	"""gen filter for a type check"""
	return lambda x: isinstance(x, t)


def genSeqFilter(seq):
	"""gen filter for a sequence pattern"""
	# Define these values as constants outside of the filt() function so that
	# the filter will not have to re-calculate the values every time it's called.
	lastFilter = None
	if isinstance(seq, list) and seq:
		lastFilter = genFilter(seq[-1])
		seq = seq[:-1]
	seqType = type(seq)
	seqLen = len(seq)
	subFilters = [genFilter(pattern) for pattern in seq]
	seqRange = range(seqLen)
	def filt(x):
		"""resulting filter function"""
		if not isinstance(x, seqType):
			return False
		if len(x) < seqLen:
			return False
		for i in seqRange:
			if not subFilters[i](x[i]):
				return False
			# end if
		for value in x[seqLen:]:
			# Don't allow any excess values if lastFilter hasn't been set.
			if lastFilter is None or not lastFilter(value):
				return False
			# end if
		return True
	return filt


def genDictFilter(dict_):
	"""gen filter for a dictionary pattern"""
	subFilters = []
	for key, pattern in dict_.items():
		subFilters.append((key, genFilter(pattern)))
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
