import tarfile, json, os, collections
src="/home/claude/public_mas/raw/tmpxv7__who-when-pro/data_release.tar.gz"
out="/home/claude/public_mas/raw/wwp_json"
os.makedirs(out,exist_ok=True)
t=tarfile.open(src,"r|gz")
inv=[]; media=collections.Counter(); mediasz=collections.Counter()
for m in t:
    parts=m.name.split("/")
    if m.isdir(): continue
    if m.name.endswith(".json") and len(parts)==5:
        rec=dict(path=m.name,modality=parts[1],benchmark=parts[2],framework=parts[3],kind="file" if m.isfile() else ("symlink" if m.issym() else "other"),link=m.linkname or None)
        if m.isfile():
            dst=os.path.join(out,"__".join(parts[1:]))
            with open(dst,"wb") as f: f.write(t.extractfile(m).read())
            rec["local"]=dst
        inv.append(rec)
    else:
        ext=parts[-1].rsplit(".",1)[-1] if "." in parts[-1] else "<none>"
        media[(parts[1] if len(parts)>1 else "?",ext,"file" if m.isfile() else "symlink" if m.issym() else "other")]+=1
        mediasz[(parts[1] if len(parts)>1 else "?",ext)]+=m.size
json.dump(dict(inventory=inv,media={"|".join(k):v for k,v in media.items()},media_bytes={"|".join(k):v for k,v in mediasz.items()}),open("/home/claude/public_mas/wwp_inventory.json","w"),indent=0)
print(len(inv), collections.Counter((r["modality"],r["kind"]) for r in inv))
