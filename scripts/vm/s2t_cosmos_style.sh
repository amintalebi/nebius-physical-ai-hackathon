set -uo pipefail
W=~/work; S=$W/s2t; L=$W/logs; CV=$W/cosmos-transfer2.5/.venv/bin/python
rm -rf $W/work/cosmos_style $W/data/cosmos/A30_style
$CV $S/scripts/cosmos_transfer_batch.py prepare --dataset $W/datasets/local/sim_A_30 --work $W/work/cosmos_style --gpus 1 --stride 6 \
  --style-image $S/configs/cosmos/station_reference.jpg --prompts $W/s2t_pr6/configs/cosmos/station_prompts.txt \
  --model edge/distilled --num-steps 4 --edge-weight 1.0 --edge-threshold low
$CV $S/scripts/cosmos_transfer_batch.py run --work $W/work/cosmos_style --cosmos-repo $W/cosmos-transfer2.5
$CV $S/scripts/cosmos_transfer_batch.py assemble --dataset $W/datasets/local/sim_A_30 --work $W/work/cosmos_style --dst $W/data/cosmos/A30_style
echo STYLE_DONE $(date -u +%H:%M)
