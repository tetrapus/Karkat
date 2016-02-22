""" Test the functions in util.tex """

from functools import partial

from hypothesis import given, assume
from hypothesis.strategies import (
    text, sampled_from, characters, lists, integers, one_of, just,
)

import util.text as module

# pylint: disable=R0201,R0903,C0103


ENCODINGS = [
    "ascii", "big5", "big5hkscs", "cp037", "cp424", "cp437", "cp500", "cp720",
    "cp737", "cp775", "cp850", "cp852", "cp855", "cp856", "cp857", "cp858",
    "cp860", "cp861", "cp862", "cp863", "cp864", "cp865", "cp866", "cp869",
    "cp874", "cp875", "cp932", "cp949", "cp950", "cp1006", "cp1026", "cp1140",
    "cp1250", "cp1251", "cp1252", "cp1253", "cp1254", "cp1255", "cp1256",
    "cp1257", "cp1258", "euc_jp", "euc_jis_2004", "euc_jisx0213", "euc_kr",
    "gb2312", "gbk", "gb18030", "hz", "iso2022_jp", "iso2022_jp_1",
    "iso2022_jp_2", "iso2022_jp_2004", "iso2022_jp_3", "iso2022_jp_ext",
    "iso2022_kr", "latin_1", "iso8859_2", "iso8859_3", "iso8859_4",
    "iso8859_5", "iso8859_6", "iso8859_7", "iso8859_8", "iso8859_9",
    "iso8859_10", "iso8859_13", "iso8859_14", "iso8859_15", "iso8859_16",
    "johab", "koi8_r", "koi8_u", "mac_cyrillic", "mac_greek", "mac_iceland",
    "mac_latin2", "mac_roman", "mac_turkish", "ptcp154", "shift_jis",
    "shift_jis_2004", "shift_jisx0213", "utf_32", "utf_32_be", "utf_32_le",
    "utf_16", "utf_16_be", "utf_16_le", "utf_7", "utf_8", "utf_8_sig"
]


class TestEncodedSize:
    """ Tests related to encoded_size """
    @given(text(), sampled_from(ENCODINGS))
    def test_encoded_size_def(self, string, encoding):
        """
        encoded_size should return the length of a string after encoding
        """
        encoded_string = string.encode(encoding, 'replace')
        assert module.encoded_size(encoding, string) == len(encoded_string)


STRINGS = lists(text(), min_size=1).map(tuple)
SIZE = integers(min_value=0)


def _count_all(c):
    return lambda s: s.count(c)


# Examples of valid measures
MEASURES = one_of(
    sampled_from(ENCODINGS).map(
        lambda s: partial(module.encoded_size, s)
    ),
    just(len),
    just(module.striplen),
    characters().map(_count_all),
    just(str.isupper)
)


class TestJoinUntil:
    """ Tests for join_until """
    @given(text())
    def test_empty_returns_none(self, separator):
        """ join_until of an empty list is unsatisfiable """
        assert module.join_until(separator, []) is None

    @given(text(), STRINGS)
    def test_implements_join(self, separator, parts):
        """
        join_until is equivalent to str.join for non-empty lists with no
        ceiling
        """
        assert separator.join(parts) == module.join_until(separator, parts)

    @given(text(), STRINGS, MEASURES)
    def test_first_element_unsat_is_unsat(self, separator, parts, measure):
        """
        If the first element breaks the ceiling, the join is unsatisfiable
        """
        assert module.join_until(
            separator, parts, ceiling=measure(parts[0]) - 1, measure=measure
        ) is None

    @given(text(), STRINGS, SIZE, MEASURES)
    def test_obeys_ceiling(self, separator, parts, ceiling, measure):
        """
        The measure of the result of join_until is never greater than ceiling
        """
        assume(measure(parts[0]) <= ceiling)

        string = module.join_until(
            separator, parts, ceiling=ceiling, measure=measure
        )

        assert measure(string) <= ceiling

    @given(text(), STRINGS, SIZE, MEASURES)
    def test_best_ceiling(self, separator, parts, ceiling, measure):
        """
        Adding another part to the resulting string will break the ceiling
        """
        assume(measure(parts[0]) <= ceiling)

        string = module.join_until(
            separator, parts, ceiling=ceiling, measure=measure
        )
        # We rely on the equivalence with str.join and the monotonicity of
        # `measure` for this test
        for idx, _ in enumerate(parts):
            test = separator.join(parts[:idx + 1])
            if len(test) <= len(string):
                assert measure(test) <= measure(string)
            else:
                assert measure(test) > measure(string)
