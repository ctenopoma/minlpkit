import os
import glob
import re
import json
import time
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor, as_completed

translator = GoogleTranslator(source='ja', target='en')

def translate_text(text):
    if not text.strip():
        return text
    try:
        if len(text) < 4000:
            return translator.translate(text)
        else:
            chunks = []
            current = []
            current_len = 0
            for line in text.split('\n'):
                if current_len + len(line) > 3000:
                    chunks.append('\n'.join(current))
                    current = [line]
                    current_len = len(line)
                else:
                    current.append(line)
                    current_len += len(line) + 1
            if current:
                chunks.append('\n'.join(current))
            
            translated = [translator.translate(c) for c in chunks]
            return '\n'.join(translated)
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def translate_markdown(content):
    # Regex to extract frontmatter
    frontmatter = ""
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = f"---{parts[1]}---\n"
            content = parts[2]
            
    # Regex to extract code blocks and html blocks to prevent translating them
    blocks = []
    
    def replacer(match):
        blocks.append(match.group(0))
        return f"\n\n[[[BLOCK_{len(blocks)-1}]]]\n\n"
        
    content = re.sub(r'```.*?```', replacer, content, flags=re.DOTALL)
    content = re.sub(r'`[^`\n]+`', replacer, content)
    
    # Translate the remaining content
    translated_content = translate_text(content)
    
    # Restore blocks
    for i, block in enumerate(blocks):
        translated_content = translated_content.replace(f"[[[BLOCK_{i}]]]", block)
        
    return frontmatter + translated_content

def process_file(filepath):
    print(f"Processing {filepath}...")
    if filepath.endswith('.md'):
        new_filepath = filepath[:-3] + '.en.md'
        if os.path.exists(new_filepath):
            return
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        translated = translate_markdown(content)
        with open(new_filepath, 'w', encoding='utf-8') as f:
            f.write(translated)
            
    elif filepath.endswith('.ipynb'):
        new_filepath = filepath[:-6] + '.en.ipynb'
        if os.path.exists(new_filepath):
            return
            
        with open(filepath, 'r', encoding='utf-8') as f:
            nb = json.load(f)
            
        for cell in nb.get('cells', []):
            if cell['cell_type'] == 'markdown':
                source = "".join(cell['source'])
                translated = translate_markdown(source)
                # Keep original lines structure by splitting on \n
                lines = [line + '\n' for line in translated.split('\n')]
                if lines and lines[-1].endswith('\n\n'):
                    lines[-1] = lines[-1][:-1]
                cell['source'] = lines
                
        with open(new_filepath, 'w', encoding='utf-8') as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)

def main():
    md_files = glob.glob('docs/**/*.md', recursive=True)
    ipynb_files = glob.glob('docs/**/*.ipynb', recursive=True)
    
    all_files = [f for f in md_files + ipynb_files if not f.endswith('.en.md') and not f.endswith('.en.ipynb')]
    
    # Process sequentially to avoid aggressive rate limiting
    for i, f in enumerate(all_files):
        print(f"[{i+1}/{len(all_files)}] Translating {f}")
        process_file(f)
        time.sleep(1) # Be nice to the API

if __name__ == '__main__':
    main()
