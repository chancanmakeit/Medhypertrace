"""Convert build_sft.py output (sft_graph/*.jsonl or sft_text/*.jsonl) to MS-Swift rows.

in : {run_id, system, user, graph_refs [[kind, idx], ...], answer, code, ...}
out: {"messages": [{"role": "system", ...}, {"role": "user", ...}(, {"role": "assistant", "content": answer})],
      "run_id": str, "graph_refs": "<JSON string>"}    (mixed-type lists cannot be stored in an Arrow column)
Eval rows (no "answer") get no assistant turn; their metadata (inst, code, label, auditor, i) is not needed by swift
and is read back from the original file by eval_swift.py.
Usage: python prepare_data.py <in.jsonl> <out.jsonl>
"""
import json
import sys


def convert(row):
    msgs = [{'role': 'system', 'content': row['system']}, {'role': 'user', 'content': row['user']}]
    if row.get('answer') is not None:
        msgs.append({'role': 'assistant', 'content': row['answer']})
    n_ph = row['user'].count('<graph>')
    refs = row.get('graph_refs') or []
    assert n_ph == len(refs), (row.get('run_id'), n_ph, len(refs))
    return {'messages': msgs, 'run_id': str(row['run_id']), 'graph_refs': json.dumps(refs)}


def main(src, dst):
    n = 0
    with open(src) as f, open(dst, 'w') as g:
        for line in f:
            g.write(json.dumps(convert(json.loads(line)), ensure_ascii=False) + '\n'); n += 1
    print(f'{n} rows -> {dst}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
