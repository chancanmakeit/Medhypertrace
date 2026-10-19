"""Round 22: measure how often a step's LLM input contains outputs of earlier steps
(the "read-set" hyperedge), per framework, from AEGIS input_messages.
Usage: python analysis/read_hyperedge_stats.py $MHT_DATA_DIR"""
import json, glob, sys, statistics as st, collections, os
def norm(s): return ' '.join(str(s).split())
def shingles(o, k=60):
    if len(o) < k: return [o] if len(o) >= 25 else []
    step = max(1, (len(o) - k) // 4); return [o[i:i+k] for i in range(0, len(o) - k + 1, step)][:5]
for f in sorted(glob.glob(os.path.join(sys.argv[1], '*.jsonl'))):
    fw = os.path.basename(f).split('-')[-1].replace('_error.jsonl', '')
    reads_n, nsteps, agents, hit, tot, noinp, allsteps = [], [], [], 0, 0, 0, 0
    for l in open(f):
        h = json.loads(l)['injection_log']['conversation_history']
        nsteps.append(len(h)); agents.append(len(set(s.get('agent_name') for s in h)))
        outs = [norm(s.get('response') or s.get('content') or '') for s in h]; sh = [shingles(o) for o in outs]
        for i, s in enumerate(h):
            im = s.get('input_messages') or []; allsteps += 1; noinp += not im
            inp = norm(' '.join(m['content'] if isinstance(m.get('content'), str) else json.dumps(m.get('content'), ensure_ascii=False) for m in im))
            r = [j for j in range(i) if sh[j] and sum(x in inp for x in sh[j]) >= max(1, len(sh[j]) // 2)]
            if i > 0: tot += 1; hit += bool(r); reads_n.append(len(r))
    ge3 = sum(x >= 3 for x in reads_n) / len(reads_n)
    print(f"{fw:16s} traj={len(nsteps)} steps_med={st.median(nsteps)} agents_med={st.median(agents)} "
          f"read>=1={hit/tot:.0%} read>=3={ge3:.0%} missing_input={noinp/allsteps:.0%}")
