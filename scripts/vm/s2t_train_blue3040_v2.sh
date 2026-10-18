# ACT on blue A (30+40 mm, 72 eps, already merged), 8k steps, 12 loader workers; sim eval at 4k / 8k per size.
set -uo pipefail
W=~/work; L=$W/logs; LR=$W/env_lerobot/bin; R=$W/s2t_pr6
rm -rf $W/outputs/act_sim_A_blue3040
cd $W && $LR/lerobot-train --dataset.repo_id=local/sim_A_blue3040 --dataset.root=$W/data/sim/A_blue3040 \
  --dataset.image_transforms.enable=true --policy.type=act --policy.device=cuda --policy.push_to_hub=false \
  --policy.chunk_size=100 --policy.n_action_steps=100 --output_dir=$W/outputs/act_sim_A_blue3040 --job_name=act_sim_A_blue3040 \
  --steps=8000 --batch_size=32 --num_workers=12 --save_freq=4000 --log_freq=250 --seed=1000 --wandb.enable=false > $L/train_A_blue3040.log 2>&1 &
echo "training started $(date -Is)"
export OMNI_KIT_ACCEPT_EULA=YES
for step in 004000 008000; do
  ck=$W/outputs/act_sim_A_blue3040/checkpoints/$step/pretrained_model
  until [ -f $ck/model.safetensors ]; do sleep 30; done; sleep 20
  i=0
  for s in 25 30 40; do
    port=$((5900 + 10#$step / 1000 + 10 * i)); i=$((i+1))
    ( $LR/python $W/s2t/scripts/act_server.py --ckpt $ck --port $port > $L/act_server_blue_${step}_$s.log 2>&1 & srv=$!
      sleep 40
      $W/env_isaaclab/bin/python $W/s2t/scripts/eval_act_in_sim.py --starter $W/so101_sim_pickplace --station $R/configs/station.yaml \
        --per-spot 1 --size $s --policy_port $port --ckpt-name act_A_blue3040_$step --out $W/reports/sim_eval_act_A_blue3040.jsonl \
        --record_dir $L/eval_act_A_blue3040 --headless > $L/eval_act_A_blue3040_${step}_$s.log 2>&1
      echo "$step ${s}mm: $(grep "^\[eval\] act_" $L/eval_act_A_blue3040_${step}_$s.log)"
      kill $srv ) &
  done
  wait
  echo "eval $step done $(date -Is)"
done
echo CHAIN_DONE $(date -Is)
