#!/usr/bin/env python3
"""比較出力から、本文を含まない実測値を集計する。"""
import argparse
import json
from pathlib import Path


def union(intervals):
    merged = []
    for a, b in sorted(intervals):
        if b <= a:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def intersection_seconds(a, b):
    i = j = 0
    seconds = 0.0
    while i < len(a) and j < len(b):
        seconds += max(0, min(a[i][1], b[j][1])-max(a[i][0], b[j][0]))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return seconds


def collect(root):
    meeting = json.loads((root / 'meeting-info.json').read_text(encoding='utf-8'))
    metrics = {}
    for file in root.glob('*.json'):
        report = json.loads(file.read_text(encoding='utf-8'))
        if not isinstance(report, dict) or 'wall_seconds' not in report or 'results' not in report:
            continue
        rows = report['results']
        text = ''.join(row['text'] for row in rows)
        value = {key: report[key] for key in ('engine', 'suite', 'wall_seconds', 'load_seconds',
                  'torch_peak_allocated_mib', 'torch_peak_reserved_mib')}
        value.update(chars=len(text), replacement_chars=text.count('\ufffd'), inputs=len(rows))
        if 'cer' in report:
            value.update(cer=report['cer'], reference_chars=report['reference_chars'])
        if report['suite'] != 'fleurs':
            value['observed_company_exact_mentions'] = text.count('日本電設工業')
            segments = [dict(s, start=row['start']+s['start'], end=row['start']+s['end'])
                        for row in rows for s in (row.get('segments') or [])]
            if segments:
                start, end = min(row['start'] for row in rows), max(row['end'] for row in rows)
                vad = union([(max(start,v['start']), min(end,v['end'])) for v in meeting['vad']])
                covered = union([(s['start'],s['end']) for s in segments if s['text'].strip()])
                vad_seconds = sum(b-a for a,b in vad)
                value.update(segments=len(segments), last_segment_end=max(s['end'] for s in segments),
                    segments_outside_input=sum(s['start'] < 0 or s['end'] > row['end']-row['start']
                                               for row in rows for s in row['segments']),
                    backwards_segment_starts=sum(b['start'] < a['start'] for row in rows
                                                 for a,b in zip(row['segments'],row['segments'][1:])),
                    vad_seconds=vad_seconds, vad_uncovered_seconds=vad_seconds-intersection_seconds(vad,covered),
                    vad_interval_coverage=intersection_seconds(vad,covered)/vad_seconds,
                    speaker_counts_per_input=[len({s['speaker'] for s in row['segments'] if s['speaker']}) for row in rows],
                    coverage_note='VAD区間と出力時刻の重なり。単語の欠落率・時刻の正解率ではない')
            else:
                value['coverage_note'] = '文字時刻を出さないため未計測'
        metrics[file.stem] = value
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.root), ensure_ascii=False, indent=2))
