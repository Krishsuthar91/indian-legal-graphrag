import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path('.').resolve()))

hierarchy_dir = pathlib.Path('data/hierarchy')
# Find which files have n_0018
for f in sorted(hierarchy_dir.glob('*.json')):
    d = json.load(open(f, encoding='utf-8'))
    nodes = d.get('nodes', [])
    for n in nodes:
        if n.get('node_id') == 'n_0018':
            doc_id = d.get('document_id', '?')
            print("File: %s (doc=%s) n_0018 = num=%s title=%s" % (
                f.name, doc_id[:12],
                n.get('numbering', '?'),
                n.get('title', '')[:50]
            ))
            break
