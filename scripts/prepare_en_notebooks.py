import glob
import json
import os

def strip_outputs_and_copy():
    ipynbs = glob.glob('docs/**/*.ipynb', recursive=True)
    for path in ipynbs:
        if path.endswith('.en.ipynb'):
            continue
        
        out_path = path[:-6] + '.en.ipynb'
        # Skip if already exists
        if os.path.exists(out_path):
            continue
            
        with open(path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
            
        # Strip outputs
        for cell in nb.get('cells', []):
            if 'outputs' in cell:
                cell['outputs'] = []
            if 'execution_count' in cell:
                cell['execution_count'] = None
                
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)
            
        print(f"Created stripped {out_path}")

if __name__ == '__main__':
    strip_outputs_and_copy()
