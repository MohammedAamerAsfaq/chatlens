#!/usr/bin/env python3
"""Filter MLX training candidates using the exact model tokenizer, before LoRA."""
import argparse
import json
from pathlib import Path
from mlx_lm.utils import load_tokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--max-seq-length', type=int, default=2048)
    args = parser.parse_args()
    if args.max_seq_length < 128:
        parser.error('max-seq-length must be at least 128')
    output = Path(args.output_dir)
    if output.exists() and any(output.iterdir()):
        parser.error('output directory must be new or empty')
    tokenizer = load_tokenizer(args.model)
    kept, skipped = [], 0
    with Path(args.input).open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            tokens = tokenizer.apply_chat_template(row['messages'], return_dict=False)
            if len(tokens) > args.max_seq_length:
                skipped += 1
            else:
                kept.append(row)
    if not kept:
        raise SystemExit('No examples fit the token limit; no training data written.')
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'train.jsonl').open('x', encoding='utf-8') as stream:
        for row in kept:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'Kept {len(kept)} examples; excluded {skipped} over {args.max_seq_length} tokens.')


if __name__ == '__main__':
    main()
