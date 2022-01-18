#!/usr/bin/python3

# Copyright 2020 Josh Bailey (josh@vandervecken.com)

## Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

## The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

import argparse
import sys
import numpy as np
import pandas as pd
from collections import defaultdict

from fileio import out_path
from sidlib import remove_end_repeats

parser = argparse.ArgumentParser(description='Downsample SSFs')
parser.add_argument('ssffile', help='SSF file')
parser.add_argument('--sample_cycles', default=7000, type=int, help='sample interval in CPU cycles')
parser.add_argument('--max_cycles', default=25e4, type=int, help='include number of CPU cycles')

args = parser.parse_args()
sample_count = int(args.max_cycles / args.sample_cycles) + 1
waveform_cols = {'sync1': 'S', 'ring1': 'R', 'tri1': 't', 'saw1': 's', 'pulse1': 'p', 'noise1': 'n'}
adsr_cols = {'atk1', 'dec1', 'sus1', 'rel1'}
sid_cols = {
    'freq1', 'pwduty1', 'gate1', 'test1', 'vol',
    'fltlo', 'fltband', 'flthi', 'flt1', 'fltext', 'fltres', 'fltcoff',
    'freq3', 'test3'}.union(waveform_cols.keys()).union(adsr_cols)
big_regs = {'freq1': 8, 'freq3': 8, 'pwduty1': 4, 'fltcoff': 3}
sample_df = pd.DataFrame([{'clock': i * args.sample_cycles} for i in range(sample_count)], dtype=np.int64)
sample_max = sample_df['clock'].max()
redundant_adsr_cols = set()
for col in adsr_cols:
    for clock in sample_df[sample_df['clock'] > 0]['clock'].unique():
        redundant_adsr_cols.add((col, '_'.join((col, str(clock)))))

df = pd.read_csv(args.ssffile, dtype=pd.Int64Dtype())
if len(df) < 1:
    sys.exit(0)
df['clock'] = df['clock'].astype(np.int64)
df = df[df['clock'] <= sample_max]
for col, bits in big_regs.items():
    df[col] = np.left_shift(np.right_shift(df[col], bits), bits)
meta_cols = set(df.columns) - sid_cols
df_raws = defaultdict(list)
for hashid, ssf_df in df.groupby(['hashid']):  # pylint: disable=no-member
    resample_df = pd.merge_asof(sample_df, ssf_df).astype(pd.Int64Dtype())
    cols = (set(resample_df.columns) - meta_cols)
    df_raw = {col: resample_df[col].iat[-1] for col in meta_cols - {'clock', 'frame'}}
    waveforms = []
    for row in resample_df.itertuples():
        row_waveforms = {mapped_col: getattr(row, waveform_col, 0) for waveform_col, mapped_col in waveform_cols.items()}
        row_waveforms = sorted([
            waveform_col for waveform_col, waveform_val in row_waveforms.items() if pd.notna(waveform_val) and waveform_val != 0])
        if row_waveforms:
            row_waveforms = ''.join(row_waveforms)
        else:
            row_waveforms = '0'
        if not waveforms or row_waveforms != waveforms[-1]:
            waveforms.append(row_waveforms)
            waveforms = remove_end_repeats(waveforms)
        time_cols = {(col, '%s_%u' % (col, row.clock)) for col in cols} - redundant_adsr_cols
        df_raw.update({time_col: getattr(row, col) for col, time_col in time_cols})
    for col in big_regs:
        col_raw = resample_df[resample_df[col].notna()][col]
        col_diff = col_raw.diff()
        for col_title, col_var in (
                ('%s_mindiff' % col, col_diff.min()),
                ('%s_maxdiff' % col, col_diff.max()),
                ('%s_meandiff' % col, col_diff.mean()),
                ('%s_nunique' % col, col_raw.nunique())):
            df_raw[col_title] = pd.NA
            if pd.notna(col_var):
                df_raw[col_title] = int(col_var)

    waveforms = '-'.join(waveforms)
    df_raws[waveforms].append(df_raw)


for waveforms, dfs in df_raws.items():
    df = pd.DataFrame(dfs, dtype=pd.Int64Dtype()).set_index('hashid')
    nacols = [col for col in df.columns if df[col].isnull().all() or df[col].max() == 0]
    df = df.drop(nacols, axis=1).drop_duplicates()
    outfile = out_path(args.ssffile, 'resample_ssf.%s.xz' % waveforms)
    df.to_csv(outfile)
