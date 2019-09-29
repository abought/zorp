# ZORP: A helpful GWAS parser

[![Build Status](https://api.travis-ci.org/abought/zorp.svg?branch=develop)](https://api.travis-ci.org/abought/zorp)

## Why?
ZORP is intended to abstract away differences in file formats, and help you work with GWAS data from many 
different sources.

- Provide a single unified interface to read text, gzip, or tabixed data
- Separation of concerns between reading and parsing (with parsers that can handle the most common file formats)
- Includes helpers to auto-detect data format and filter for variants of interest 

## Why not?
ZORP provides a high level abstraction. This means that it is convenient, at the expense of speed.

For GWAS files, ZORP does not sort the data for you, because doing so in python would be quite slow. You will still 
need to do some basic data preparation before using.

## Usage
### Python
```python
from zorp import readers, parsers

# Create a reader instance. This example specifies each option for clarity, but sniffers are provided to auto-detect 
#   common format options.
sample_parser = parsers.GenericGwasLineParser(marker_col=1, pvalue_col=2, is_neg_log_pvalue=True,
                                              delimiter='\t')
reader = readers.TabixReader('input.bgz', parser=sample_parser, skip_rows=1, skip_errors=True)

# After parsing the data, values of pre-defined fields can be cleaned up, or used to perform lookups
reader.add_transform('rsid', lambda variant: some_rsid_finder(variant.chrom, variant.pos, variant.ref, variant.alt))

# We can filter data to the variants of interest. If you use a domain specific parser, columns can be referenced by name
reader.add_filter('chrom', '19')  # This row must have the specified value for the "chrom" field
reader.add_filter(lambda row: row.neg_log_pvalue > 7.301)  # Provide a function that can operate on all parsed fields
reader.add_filter('neg_log_pvalue')  # Exclude values with missing data for the named field  

# Iteration returns containers of cleaned, parsed data (with fields accessible by name).
for row in reader:
    print(row.chrom)

# Tabix files support iterating over all or part of the file
for row in reader.fetch('X', 500_000, 1_000_000):
    print(row)

# Write a compressed, tabix-indexed file containing the subset of variants that match filters, choosing only specific 
#   columns. The data written out will be cleaned and standardized by the parser into a well-defined format. 
out_fn = reader.write('outfile.txt', columns=['chrom', 'pos', 'pvalue'], make_tabix=True)

# Real data is often messy. If a line fails to parse, the problem will be recorded.
for number, message, raw_line in reader.errors:
    print('Line {} failed to parse: {}'.format(number, message))

```

### Command line file conversion
The file conversion feature of zorp is also available as a command line utility. See `zorp-convert --help` for details
and the full list of supported options.

This utility is currently in beta; please inspect the results carefully.

To auto-detect columns based on a library of commonly known file formats:

`$ zorp-convert --auto infile.txt --dest outfile.txt --compress`

Or specify your data columns exactly: 

`$ zorp-convert infile.txt --dest outfile.txt --index  --skip-rows 1 --chrom_col 1 --pos_col 2 --ref_col 3 --alt_col 4 --pvalue_col 5 --beta_col 6 --stderr_beta_col 7 --allele_freq_col 8`

The `--index` option requires that your file be sorted first. If not, you can tabix the standard output format manually 
as follows.

```
$ (head -n 1 <filename.txt> && tail -n +2 <file> | sort -k1,1 -k 2,2n) | bgzip > <filename.sorted.gz>
$ tabix <filename.sorted.gz> -p vcf
```

## Development

To install dependencies and run in development mode:

`pip install -e '.[test,perf]'`

To run unit tests, use

```bash
$ flake8 zorp
$ mypy zorp
$ pytest tests/
```
