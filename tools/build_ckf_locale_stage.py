"""Extract the CKF locale snapshot and stage the Korean locale payload.

Uses only the locale/install modules so that a patch build does not need the
model pipeline. Translations and the verified font bundle are private inputs.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gloc.ckf import extract
from gloc.ckf_install import CHINESE, ENGLISH, stage
from gloc.util import GlocError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('extract', help='Write source snapshot from the original game locales')
    a.add_argument('--game', type=Path, required=True)
    a.add_argument('--out', type=Path, required=True)
    a.add_argument('--metadata', type=Path)
    a.add_argument('--target-duplicates', type=Path)
    a = sub.add_parser('stage', help='Render zh-CN locale and copy the verified font bundle')
    for name in ('snapshot', 'translations', 'game', 'font', 'out'):
        a.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'extract':
            result = extract(args.game / ENGLISH, args.game / CHINESE, args.out,
                             args.metadata, args.target_duplicates)
        else:
            result = stage(args.snapshot, args.translations, args.game, args.font, args.out, poc=True)
    except GlocError as exc:
        parser.exit(2, f'error: {exc}\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
