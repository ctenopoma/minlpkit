import json

def on_page_content(html, page, config, files):
    """
    Called after the Markdown text is rendered to HTML (but before being passed to a template).
    We inject the original Markdown into a hidden script tag so the frontend JS can access it.
    """
    if not hasattr(page, 'markdown') or not page.markdown:
        return html
        
    # Serialize markdown to JSON string
    raw_md = page.markdown
    safe_json = json.dumps(raw_md)
    
    # Escape </ to prevent breaking out of the script tag if the markdown contains </script>
    safe_json = safe_json.replace('</', '<\\/')
    
    injection = f'\n<script id="raw-markdown-data" type="application/json">{safe_json}</script>\n'
    return html + injection
