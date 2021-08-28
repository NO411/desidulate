#!/usr/bin/python3

# Copyright 2020 Josh Bailey (josh@vandervecken.com)

## Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

## The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

import argparse
import numpy as np
import pandas as pd

from fileio import wav_path
from sidlib import get_sid, timer_args
from sidwav import df2wav
from sidmidi import SidMidiFile, midi_args
from ssf import add_freq_notes_df, SidSoundFragment


parser = argparse.ArgumentParser(description='Convert .ssf into a WAV file')
parser.add_argument('ssffile', default='', help='ssf to read')
parser.add_argument('hashid', default=0, help='hashid to reproduce')
parser.add_argument('--wavfile', default='', help='WAV file to write')
skiptest_parser = parser.add_mutually_exclusive_group(required=False)
skiptest_parser.add_argument('--skiptest', dest='skiptest', action='store_true', help='skip initial SSF period where test1 is set')
skiptest_parser.add_argument('--no-skiptest', dest='skiptest', action='store_false', help='do not skip initial SSF period where test1 is set')
timer_args(parser)
midi_args(parser)
args = parser.parse_args()

sid = get_sid(pal=args.pal)
smf = SidMidiFile(sid, args.bpm)
wavfile = args.wavfile
if not wavfile:
    wavfile = wav_path(args.ssffile)

df = pd.read_csv(args.ssffile, dtype=pd.Int64Dtype())
hashid = np.int64(args.hashid)
ssf_df = df[df['hashid'] == hashid].copy()

if len(ssf_df):
    ssf_df = add_freq_notes_df(sid, ssf_df)
    ssf_df = ssf_df.fillna(method='ffill').set_index('clock')
    ssf = SidSoundFragment(args.percussion, sid, ssf_df, smf)
    df2wav(ssf_df, sid, wavfile, skiptest=args.skiptest)
    print(ssf_df.to_string())
    print(ssf.instrument({}))
else:
    print('SSF %d not found' % hashid)
