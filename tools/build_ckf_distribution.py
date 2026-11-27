"""Build an explicitly authorized CKF Windows delta ZIP from verified local stages."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gloc.ckf_distribution import build_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', required=True, type=Path)
    parser.add_argument('--stage', required=True, action='append', type=Path)
    parser.add_argument('--build', required=True)
    parser.add_argument('--game-version', required=True)
    parser.add_argument('--revision', type=int, default=0)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--authorize-package', action='store_true', required=True,
                        help='Explicit package assembly authority; does not assert language/full-game QA approval')
    parser.add_argument('--allow-partial-images', action='store_true',
                        help='Explicitly package incomplete current-build images with hash-bound partial evidence and a visible notice')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = build_package(stages=args.stage, original=args.original,
                           templates=root/'templates/ckf-distribution',
                           font_license=root/'licenses/NotoSansCJK-OFL.txt',
                           font_notice='Noto Sans CJK KR Regular, Version 2.004\n© 2014-2021 Adobe (http://www.adobe.com/).',
                           build=args.build, game_version=args.game_version, revision=args.revision,
                           out=args.out, work=args.work, allow_partial_images=args.allow_partial_images)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
