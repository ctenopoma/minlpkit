document.addEventListener("DOMContentLoaded", function() {
    var scriptTag = document.getElementById('raw-markdown-data');
    if (!scriptTag) return;
    
    var rawMd = "";
    try {
        rawMd = JSON.parse(scriptTag.textContent);
    } catch (e) {
        console.error("Failed to parse raw markdown data", e);
        return;
    }
    
    // Create floating button
    var btn = document.createElement('button');
    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path><rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect></svg> MDでコピー';
    
    // Style the button (modern floating look)
    btn.style.position = 'fixed';
    btn.style.bottom = '30px';
    btn.style.right = '30px';
    btn.style.zIndex = '9999';
    btn.style.padding = '12px 20px';
    btn.style.backgroundColor = 'var(--md-primary-fg-color, #2563eb)';
    btn.style.color = 'white';
    btn.style.border = 'none';
    btn.style.borderRadius = '30px';
    btn.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)';
    btn.style.cursor = 'pointer';
    btn.style.fontWeight = 'bold';
    btn.style.display = 'flex';
    btn.style.alignItems = 'center';
    btn.style.justifyContent = 'center';
    btn.style.transition = 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.2s';
    btn.style.fontFamily = 'inherit';
    btn.style.fontSize = '0.9rem';
    
    // Hover effects
    btn.onmouseover = function() { 
        btn.style.transform = 'translateY(-2px)'; 
        btn.style.boxShadow = '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)';
    };
    btn.onmouseout = function() { 
        btn.style.transform = 'translateY(0)'; 
        btn.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)';
    };
    
    // Click action
    btn.onclick = function() {
        navigator.clipboard.writeText(rawMd).then(function() {
            var oldHtml = btn.innerHTML;
            var oldBg = btn.style.backgroundColor;
            
            btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!';
            btn.style.backgroundColor = '#10b981'; // Success green
            btn.style.transform = 'scale(1.05)';
            
            setTimeout(function() {
                btn.innerHTML = oldHtml;
                btn.style.backgroundColor = oldBg;
                btn.style.transform = 'scale(1)';
            }, 2000);
        }).catch(function(err) {
            console.error('Could not copy text: ', err);
            alert("コピーに失敗しました。");
        });
    };
    
    document.body.appendChild(btn);
});
