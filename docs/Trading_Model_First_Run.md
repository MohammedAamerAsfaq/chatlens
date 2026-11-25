# First local trading parser training run

This experiment fine-tunes a pretrained 4-bit Qwen model using MLX LoRA on Apple silicon. It covers text inquiry detection, direction and product line extraction. Contact ranking and market intelligence are separate work. It does not alter the running ChatLens parser.

## Data

On the ChatLens server, prepare a new dataset directory:

```powershell
venv\Scripts\python.exe manage.py prepare_trading_mlx_dataset --company-id 1 --output-dir training_data/trading_v1
```

The directory must be new or empty. `candidates.jsonl` contains the original message and its selected label. It may contain phone numbers and confidential trading content; keep it private and transfer it to the Mac through an approved secure channel. The directory is ignored by Git. `manifest.json` contains aggregate counts, and `provenance.jsonl` records the origin and group of each candidate in matching order. The command uses the active stored labels, prioritizes a human label over an AI label within a duplicate group, skips conflicting labels of the chosen provenance, and excludes groups assigned to validation or test. Duplicate grouping is heuristic and does not identify every paraphrased broadcast.

AI labels are unverified drafts. Product details can be wrong or incomplete. This is an experiment, not a ground-truth dataset. Notes and reviewer identities are not placed in model answers. The prepared data is a snapshot; to incorporate later corrections, generate another new directory.

## On the Mac

Copy `candidates.jsonl`, `filter_mlx_data.py` and `train_mlx.sh` to the Mac. Run from the directory containing the scripts:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip mlx-lm
sh train_mlx.sh /path/to/candidates.jsonl /path/to/new-private-run
```

The model and tokenizer download on first use. By default the script uses `mlx-community/Qwen3-4B-Instruct-2507-4bit`, 300 training iterations, a batch size of one, and a 2,048-token sequence limit. It tokenizes each complete chat example with the chosen model's tokenizer and excludes examples that do not fit; it does not truncate the answer. It prints the number excluded. The resulting dataset is in `NEW_RUN_DIRECTORY/data/train.jsonl`, and trained adapter weights are saved in `NEW_RUN_DIRECTORY/adapters/`. A new run directory is required to avoid overwriting prior artifacts.

The example settings are a starting point, not a tested memory or performance guarantee for the 24 GB M4. Optional environment variables are `TRADING_MODEL`, `TRADING_ITERS`, and `TRADING_MAX_SEQ_LENGTH`. Increasing the sequence length increases memory use. Training without a validation set is intentional for this initial experiment; no accuracy or loss-based model-selection claim is implied.

The 4-bit model is an MLX conversion of Qwen3-4B-Instruct-2507: https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit. MLX LM's training format and options are documented at https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md.
