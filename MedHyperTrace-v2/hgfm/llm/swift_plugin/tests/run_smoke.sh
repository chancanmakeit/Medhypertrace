#!/usr/bin/env bash
# (d) 10-step `swift sft` for both variants on the synthetic fold (CPU, fp32, tiny model), then (e) on each checkpoint.
# Usage: bash run_smoke.sh <tiny model dir or id> <synthetic dir from make_synthetic.py + prepare_data.py> [steps=10]
set -euo pipefail
LM=$1; SYN=$2; STEPS=${3:-10}
P=$(cd "$(dirname "$0")/.." && pwd)
export USE_HF=1 MHT_GRAPH_TOKENS=$SYN/graph_tokens.pt
for V in graph text; do
  swift sft --external_plugins $P/plugin.py \
    --model $LM --model_type graph_token_lm --template graph_token \
    --tuner_type graph_lora --lora_rank 8 --lora_alpha 32 --lora_dropout 0.1 --target_modules q_proj k_proj v_proj \
    --optimizer graph_token --learning_rate 1e-4 --aligner_lr 1e-3 --weight_decay 0 \
    --lr_scheduler_type constant --warmup_ratio 0 --max_grad_norm 1.0 \
    --per_device_train_batch_size 2 --gradient_accumulation_steps 2 --max_steps $STEPS --num_train_epochs 100 \
    --max_length 512 --torch_dtype float32 --gradient_checkpointing true \
    --dataset $SYN/sft_$V/swift_train.jsonl --split_dataset_ratio 0 --strict true --dataloader_num_workers 0 \
    --save_steps $STEPS --save_only_model true --logging_steps 1 --seed 0 \
    --output_dir $SYN/out_$V --report_to none
  CK=$(ls -d $SYN/out_$V/v*/checkpoint-$STEPS | tail -1)
  ls -la $CK
  python $P/tests/test_equivalence.py --lm $LM --syn $SYN --only e --ckpt $CK --variant $V
done
