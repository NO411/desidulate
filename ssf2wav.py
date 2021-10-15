#!/usr/bin/python3

# Copyright 2020 Josh Bailey (josh@vandervecken.com)

## Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

## The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

import argparse
import os
import sys
import numpy as np
import pandas as pd

from fileio import wav_path, out_path
from sidlib import get_sid, timer_args
from sidwav import df2wav
from sidmidi import SidMidiFile, midi_args
from ssf import add_freq_notes_df, SidSoundFragment


parser = argparse.ArgumentParser(description='Convert .ssf into a WAV file')
parser.add_argument('ssffile', default='', help='ssf to read')
parser.add_argument('hashid', default=0, help='hashid to reproduce, or 0 if all')
parser.add_argument('--wavfile', default='', help='WAV file to write')
play_parser = parser.add_mutually_exclusive_group(required=False)
play_parser.add_argument('--play', dest='play', action='store_true', help='play the wavfile')
play_parser.add_argument('--no-play', dest='play', action='store_false', help='do not play the wavfile')
skiptest_parser = parser.add_mutually_exclusive_group(required=False)
skiptest_parser.add_argument('--skiptest', dest='skiptest', action='store_true', help='skip initial SSF period where test1 is set')
skiptest_parser.add_argument('--no-skiptest', dest='skiptest', action='store_false', help='do not skip initial SSF period where test1 is set')
single_waveform_parser = parser.add_mutually_exclusive_group(required=False)
single_waveform_parser.add_argument('--skip-single-waveform', dest='skip_single_waveform', action='store_true', help='skip SSFs that use only a single waveform')
single_waveform_parser.add_argument('--no-skip-single-waveform', dest='skip_single_waveform', action='store_false', help='do not skip SSFs that use only a single waveform')
waveform0_parser = parser.add_mutually_exclusive_group(required=False)
waveform0_parser.add_argument('--skip-waveform0', dest='skip_waveform0', action='store_true', help='skip SSFs that use waveform 0')
waveform0_parser.add_argument('--no-skip-waveform0', dest='skip_waveform0', action='store_false', help='do not skip SSFs that use waveform 0')
timer_args(parser)
midi_args(parser)
args = parser.parse_args()

sid = get_sid(pal=args.pal)
smf = SidMidiFile(sid, args.bpm)
df = pd.read_csv(args.ssffile, dtype=pd.Int64Dtype())
hashid = np.int64(args.hashid)

if not len(df):
    print('empty SSF file')
    sys.exit(0)


def render_wav(ssf_df, wavfile):
    ssf_df = add_freq_notes_df(sid, ssf_df)
    ssf_df = ssf_df.fillna(method='ffill').set_index('clock')
    ssf = SidSoundFragment(args.percussion, sid, ssf_df, smf)
    df2wav(ssf_df, sid, wavfile, skiptest=args.skiptest)
    print(ssf_df.to_string())
    print(ssf.instrument({}))
    if args.play:
        os.system(' '.join(['aplay', wavfile]))


if hashid:
    wavfile = args.wavfile
    if not wavfile:
        wavfile = wav_path(args.ssffile)

    ssf_df = df[df['hashid'] == hashid].copy()

    if len(ssf_df):
        render_wav(ssf_df, wavfile)
    else:
        print('SSF %d not found' % hashid)
else:
    waveforms = {'pulse1', 'saw1', 'tri1', 'noise1'}

    def single_waveform_filter(ssf_df, w1, w2, w3, w4):
        return ssf_df[w1].max() == 1 and ssf_df[w2].max() != 1 and ssf_df[w3].max() != 1 and ssf_df[w4].max() != 1

    def waveform0(ssf_df):
        return len(ssf_df[(ssf_df['test1'] == 0) & (ssf_df['pulse1'] != 1) & (ssf_df['saw1'] != 1) & (ssf_df['tri1'] != 1) & (ssf_df['noise1'] != 1)])

    for hashid, ssf_df in df.groupby('hashid'):
        skip = False
        if args.skip_single_waveform:
            for waveform in waveforms:
                other_waveforms = list(waveforms - {waveform})
                if single_waveform_filter(ssf_df, waveform, other_waveforms[0], other_waveforms[1], other_waveforms[2]):
                    skip = True
                    break
        if args.skip_waveform0 and waveform0(ssf_df):
            skip = True
        if skip:
            continue
        wavfile = out_path(args.ssffile, '%u.wav' % hashid)
        render_wav(ssf_df, wavfile)
