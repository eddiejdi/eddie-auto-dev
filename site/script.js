document.addEventListener('DOMContentLoaded', function(){
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');
  function activate(target){
    tabs.forEach(t=> t.classList.toggle('active', t.dataset.target===target));
    panels.forEach(p=> p.classList.toggle('active', p.id===target));
    // Lazy-load openwebui iframe only when tab is active
    if(target==='openwebui'){
      const iframe = document.getElementById('openwebuiIframe');
      const status = document.getElementById('openwebuiStatus');
      const directLink = document.getElementById('openwebuiDirectLink');
      if(iframe && !iframe.src){
        // Try reading a config file first
        fetch('/openwebui-config.json').then(r=>{
          if(!r.ok) throw new Error('no config');
          return r.json();
        }).then(cfg=>{
          if(cfg && cfg.openwebui_url){
            iframe.src = cfg.openwebui_url;
            directLink.href = cfg.openwebui_url;
            status.innerHTML = `<p>Carregando Open WebUI de <strong>${cfg.openwebui_url}</strong>. Se houver problemas, verifique o proxy/URL configurado.</p>`;
          } else {
            iframe.src = '/openwebui/';
            directLink.href = 'http://localhost:3000';
            status.innerHTML = `<p>Carregando via proxy local <code>/openwebui/</code>. Se não funcionar, abra <a href="http://localhost:3000" target="_blank">http://localhost:3000</a>.</p>`;
          }
        }).catch(()=>{
          // Fallback: try local proxy path, else show direct link
          iframe.src = '/openwebui/';
          directLink.href = 'http://localhost:3000';
          status.innerHTML = `<p>Carregando via proxy local <code>/openwebui/</code> (se disponível). Configure <code>openwebui-config.json</code> to point a um servidor público.</p>`;
        });
      }
    }
  }
  tabs.forEach(t=> t.addEventListener('click', ()=> activate(t.dataset.target)));

  // keyboard nav
  document.addEventListener('keyup', e=>{
    if(e.key==='ArrowLeft' || e.key==='ArrowRight'){
      const arr = Array.from(tabs);
      const idx = arr.findIndex(t=>t.classList.contains('active'));
      const next = e.key==='ArrowRight' ? (idx+1)%arr.length : (idx-1+arr.length)%arr.length;
      arr[next].click();
    }
  });
});