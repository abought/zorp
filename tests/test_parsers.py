"""Test line parsers"""

import math

import pytest

from zorp import (
    exceptions,
    parsers,
    parser_utils,
)


class TestBasicVariantContainerHelpers:
    @classmethod
    def setup_class(cls):
        vals = ('1', 2, 'A', 'G', math.inf, 0.1, 0.1, 0.75)
        container = parsers.BasicVariant(*vals)

        cls.vals = vals
        cls.container = container

    def test_pvalue_helpers(self):
        assert math.isinf(self.container.neg_log_pvalue)
        assert self.container.pval == 0
        assert self.container.pvalue == 0

    def test_iterates_in_predictable_field_order(self):
        iter_vals = tuple(v for v in self.vals)
        assert iter_vals == self.vals

    def test_maf_means_minor_means_lt_half(self):
        assert self.container.maf == 0.25, 'Correctly orients MAF to minor'

        vals = ('1', 2, 'A', 'G', math.inf, 0.1, 0.1, None)
        assert parsers.BasicVariant(*vals).maf is None, "Doesn't convert missing data"

    def test_dict_serialization(self):
        actual = self.container.to_dict()
        expected = {
            'chrom': '1',
            'pos': 2,
            'ref': 'A',
            'alt': 'G',
            'neg_log_pvalue': math.inf,
            'beta': 0.1,
            'stderr_beta': 0.1,
            'alt_allele_freq': 0.75,
        }

        assert actual == expected


class TestGenericGwasParser:
    def test_validates_arguments_required_fields(self):
        with pytest.raises(exceptions.ConfigurationException, match='all required'):
            parsers.GenericGwasLineParser(marker_col=1, pvalue_col=None)

    def test_validates_arguments_optional_fields(self):
        with pytest.raises(exceptions.ConfigurationException, match='all required'):
            parsers.GenericGwasLineParser(marker_col=1, pvalue_col=None)

    def test_validates_frequency_fields(self):
        with pytest.raises(exceptions.ConfigurationException, match='mutually exclusive'):
            parsers.GenericGwasLineParser(marker_col=1, pvalue_col=2, allele_count_col=3, allele_freq_col=4)

        with pytest.raises(exceptions.ConfigurationException, match='n_samples'):
            parsers.GenericGwasLineParser(marker_col=1, pvalue_col=2, allele_count_col=3, n_samples_col=None)

    def test_can_convert_to_neglogpvalue(self):
        line = '1\t100\tA\tC\t1'
        special_parser = parsers.GenericGwasLineParser(chrom_col=1, pos_col=2, ref_col=3, alt_col=4,
                                                       pvalue_col=5, is_neg_log_pvalue=True,
                                                       delimiter='\t')
        p = special_parser(line)
        assert p.neg_log_pvalue == pytest.approx(1), 'Converts -log to pvalue'
        assert p.pvalue == pytest.approx(0.1), 'Converts -log to pvalue'

    def test_can_convert_to_logpvalue_using_legacy_argument_names(self):
        line = '1\t100\tA\tC\t1'
        special_parser = parsers.GenericGwasLineParser(chrom_col=1, pos_col=2, ref_col=3, alt_col=4,
                                                       pval_col=5, is_log_pval=True,
                                                       delimiter='\t')
        p = special_parser(line)
        assert p.neg_log_pvalue == pytest.approx(1), 'Parses -logp as is'
        assert p.pvalue == pytest.approx(0.1), 'Converts -log to pvalue'

    def test_can_find_chrom_using_legacy_argument_name(self):
        line = '1\t100\tA\tC\t1'
        special_parser = parsers.GenericGwasLineParser(chr_col=1, pos_col=2, ref_col=3, alt_col=4,
                                                       pvalue_col=5, is_neg_log_pvalue=True,
                                                       delimiter='\t')
        p = special_parser(line)
        assert p.chrom == '1'

    def test_parses_marker_to_clean_format(self):
        line = 'chr2:100:A:C_anno\t.05'
        special_parser = parsers.GenericGwasLineParser(marker_col=1, pvalue_col=2, delimiter='\t')
        p = special_parser(line)
        assert p.chrom == '2', 'Finds chromosome'
        assert p.pos == 100, 'Finds position'
        assert p.ref == 'A', 'Finds ref'
        assert p.alt == 'C', 'Finds alt'
        assert p.marker == '2:100_A/C', 'Turns a messy marker into a cleaned standardized format'

    def test_warns_about_incorrect_delimiter(self):
        """
        Regression test: human-edited files may have a mix of tabs and spaces; this is hard to spot!
        """
        line = 'chr2:100:A:C_anno\t.05'
        special_parser = parsers.GenericGwasLineParser(marker_col=1, pvalue_col=2, delimiter=' ')
        with pytest.raises(exceptions.LineParseException, match="delimiter"):
            special_parser(line)

    def test_parses_freq_from_counts(self):
        line = 'chr2:100:A:C_anno\t.05\t25\t100'
        special_parser = parsers.GenericGwasLineParser(marker_col=1, pvalue_col=2,
                                                       allele_count_col=3, n_samples_col=4, is_alt_effect=False)
        p = special_parser(line)
        assert p.alt_allele_freq == 0.875, "Calculates frequency from counts and orients to alt allele"

    def test_parses_freq_from_freq(self):
        line = 'chr2:100:A:C_anno\t.05\t0.25'
        special_parser = parsers.GenericGwasLineParser(marker_col=1, pvalue_col=2,
                                                       allele_freq_col=3, is_alt_effect=True)
        p = special_parser(line)
        assert p.alt_allele_freq == 0.25, "Parses frequency as is"


class TestStandardGwasParser:
    def test_parses_locuszoom_standard_format(self):
        line = '1\t100\tA\tC\t10\t0.5\t0.5\t0.25'
        output = parsers.standard_gwas_parser(line)
        assert isinstance(output, parsers.BasicVariant)
        assert output.chrom == '1'
        assert output.pos == 100
        assert output.ref == 'A'
        assert output.alt == 'C'
        assert output.pvalue == pytest.approx(1e-10)

    def test_enforces_pos_as_int(self):
        line = '1\tNOPE\tA\tC\t0.05'
        with pytest.raises(exceptions.LineParseException, match="invalid literal"):
            parsers.standard_gwas_parser_basic(line)

    def test_handles_missing_ref(self):
        line = '1\t2\tNA\tnull\t0.05'
        output = parsers.standard_gwas_parser_basic(line)
        assert output.ref is None, 'Handles missing ref info'
        assert output.alt is None, 'Handles missing alt info'

    def test_enforces_readable_pvalue(self):
        line = '1\t100\tA\tC\tNOPE'
        with pytest.raises(exceptions.LineParseException, match="could not convert string to float"):
            parsers.standard_gwas_parser_basic(line)

    def test_handles_missing_pvalues(self):
        line = '1\t100\tA\tC\tNA'
        p = parsers.standard_gwas_parser_basic(line)
        assert p.pvalue is None, "Fills placeholder values with python None"

    def test_parses_beta_stderr_and_af(self):
        line = '1\t100\tA\tC\t10\tNA\t0.1\t0.001'
        p = parsers.standard_gwas_parser(line)
        assert p.beta is None, 'Handled missing value for beta'
        assert p.stderr_beta == 0.1, 'Parsed stderr field'
        assert p.alt_allele_freq == 0.001, 'Parsed alt allele frequency'


class TestQuickParser:
    """
    Verify that the "fast path" parser returns legible output
    """
    def test_basic_values(self):
        line = '1\t100\tA\tC\t10'
        output = parsers.standard_gwas_parser_quick(line)
        assert isinstance(output, parsers.BasicVariant)
        assert output.chrom == '1'
        assert output.pos == 100
        assert output.ref == 'A'
        assert output.alt == 'C'
        assert output.pvalue == pytest.approx(1e-10)

    def test_handles_missing_and_special_values(self):
        line = '1\t100\tnull\tNone\tInfinity'
        output = parsers.standard_gwas_parser_quick(line)
        assert isinstance(output, parsers.BasicVariant)
        assert output.chrom == '1'
        assert output.pos == 100
        assert output.ref is None
        assert output.alt is None
        assert math.isinf(output.neg_log_pvalue)

    def test_throws_errors_for_totally_invalid_line(self):
        line = '1\t100\tA\tT\tBorkborkbork'
        with pytest.raises(exceptions.LineParseException):
            parsers.standard_gwas_parser_quick(line)

    def test_fetches_extended_format_beta_stderr(self):
        """Older files will have a few core columns. Newer files will have additional fields."""
        line = '1\t100\tnull\tNone\tInfinity\t0.5\t0.1'
        output = parsers.standard_gwas_parser_quick(line)
        assert output.beta == 0.5, 'Parsed beta'
        assert output.stderr_beta == 0.1, 'Parsed stderr'

    def test_handles_explicit_missing_values_in_beta_stderr(self):
        line = '1\t100\tnull\tNone\tInfinity\tNA\t0.1'
        output = parsers.standard_gwas_parser_quick(line)
        assert output.beta is None, 'Parsed beta'
        assert output.stderr_beta == 0.1, 'Parsed stderr'

    def test_fetches_extended_format_beta_stderr_altfreq(self):
        """Older files will have a few core columns. Newer files will have additional fields."""
        line = '1\t100\tnull\tNone\tInfinity\t0.5\t0.1\t0.001'
        output = parsers.standard_gwas_parser_quick(line)
        assert output.alt_allele_freq == 0.001, 'Parsed beta'


class TestUtils:
    def test_parse_marker_fails_for_invalid_format(self):
        val = 'A_B_C_D'
        with pytest.raises(exceptions.LineParseException, match='marker format'):
            parser_utils.parse_marker(val, test=False)

    def test_pval_to_log_sidesteps_python_underflow(self):
        val = '1.93e-780'
        res = parser_utils.parse_pval_to_log(val, is_neg_log=False)
        assert res == 779.7144426909922, 'Handled value that would otherwise have underflowed'

    def test_pval_to_log_handles_external_underflow(self):
        val = '0'
        res = parser_utils.parse_pval_to_log(val)
        assert res == math.inf, 'Provides a placeholder when the input data underflowed'

        val = '0.0'
        res = parser_utils.parse_pval_to_log(val)
        assert res == math.inf, 'Provides a placeholder when the input data underflowed (slow path)'

    def test_pval_to_log_converts_to_log(self):
        val = '0.1'
        res = parser_utils.parse_pval_to_log(val)
        assert res == 1, 'Converts a regular value correctly'

    def test_pval_to_log_handles_already_log(self):
        val = '7.3'
        res = parser_utils.parse_pval_to_log(val, is_neg_log=True)
        assert res == 7.3, 'Given a string with -log10, converts data type but no other calculation'

    def test_parse_freq_given_too_many_options(self):
        with pytest.raises(exceptions.ConfigurationException, match='mutually exclusive'):
            parser_utils.parse_allele_frequency(freq='0.1', allele_count='0.2', n_samples='0.3')

    def test_parse_freq_out_of_range(self):
        with pytest.raises(ValueError):
            parser_utils.parse_allele_frequency(freq='42')

    def test_parse_freq_given_frequency(self):
        value = parser_utils.parse_allele_frequency(freq='0.25', is_alt_effect=True)
        assert value == 0.25

    def test_parse_freq_given_frequency_orients_to_alt(self):
        value = parser_utils.parse_allele_frequency(freq='0.25', is_alt_effect=False)
        assert value == 0.75

    def test_parse_freq_given_frequency_handles_missing(self):
        value = parser_utils.parse_allele_frequency(freq='NA', is_alt_effect=True)
        assert value is None

    def test_parse_freq_given_counts(self):
        value = parser_utils.parse_allele_frequency(allele_count='25', n_samples='100')
        assert value == 0.125

    def test_parse_freq_given_counts_orients_to_alt(self):
        value = parser_utils.parse_allele_frequency(allele_count='75', n_samples='100', is_alt_effect=False)
        assert value == 0.625

    def test_parse_freq_handles_missing(self):
        value = parser_utils.parse_allele_frequency(allele_count='NA', n_samples='100')
        assert value is None
