# -*- coding: utf-8 -*-

class TooDeepException(Exception):
    """
    Raised when we need to go deeper than the configured recursion level.
    """
    pass

class UnsupportedRelationException(Exception):
    """
    Raised when we encounter an unsupported relation type.
    """
    pass