import util

from hypothesis import given
from hypothesis.strategies import text

@given(text())
def test_rfc_nickkey_length(s):
    """ Test that length is maintained """
    assert len(util.rfc_nickkey(s)) == len(s)

@given(text())
def test_rfc_nickkey_normal(s):
    """ Test that rfc_nickkey is the normal form of a string """
    normal = util.rfc_nickkey(s)
    assert normal == util.rfc_nickkey(normal)