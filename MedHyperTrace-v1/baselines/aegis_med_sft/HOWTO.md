# AEGIS-med-SFT（in-domain，医学重训）— 运行说明

两个 SFT baseline 都报（已与你确认）：
- **AEGIS-SFT (OOD)**：你已有的通用数据模型 → 测医学数据。用 bridge_to_aegis_eval.py
  + 你的 evaluate-v3.py。回答"通用模型能否迁移到医学"，低分即 motivation。
- **AEGIS-med-SFT (in-domain)**：本目录，在医学数据上重训，和 HGNN 同等条件的强 baseline。

## 两个输出变体（已按你要求做成可兼容）
- `no_step`  : target = {"faulty_agents":[{agent_name,error_type}]}（忠于 AEGIS 任务定义）
- `with_step`: target = {..., "earliest_error_step": N}（轨迹级最早错误步，与 HGNN/Who&When 同口径 step Top-1）
两版都用 **instance 粒度**（Expert 0/1/2…，更贴临床）。

## 生成训练数据（本地即可，已附样例在 data_med_*/）
```
python preprocess_med_sft.py --variant no_step   --agent_key instance --out data_med_nostep
python preprocess_med_sft.py --variant with_step --agent_key instance --out data_med_withstep
```
- 用 splits.json 固定划分：train = 三框架 train tasks 合并，val = train 内按 task 留出 10%，
  test = 各框架 test tasks。与 HGNN 同划分、无泄漏。

## 在 GPU 上训练（用你仓库的 train_sft-v2.sh）
```
DATA_DIR=./data_med_nostep bash train_sft-v2.sh ./data_med_nostep ./outputs/aegis-med-sft-nostep
# with_step 同理换目录
```
train_sft-v2.sh 读 $DATA_DIR/sft/{train,val}.parquet，messages_key=messages，无需改脚本。

## 评测（统一口径）
- agent/error/pair：走 medhypertrace/aegis_metrics.py 的 compute_metrics（= 你的原版）。
- step（仅 with_step）：aegis_med.py 的 step_top1（轨迹级最早错误步 Top-1，与 HGNN/Who&When 同口径，进同一列）。
- 推理时**不要 --use_cot**（target 是直接 JSON）。
- 用 aegis_med.parse_prediction 解析模型输出（兼容两变体 + ```json 围栏）。

## 关键提醒
- with_step 现在是每条轨迹一个 earliest_error_step（= earliest_error_turn），不再是每对一个 step。
- FM 定义已替换成医学示例（14 个 code 不变）以帮助临床 grounding。
- 训练/评测必须都用 instance 粒度；若要同时报角色粒度对照，加 --agent_key role 再生成一份。
