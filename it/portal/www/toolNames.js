/* Display metadata only. Reading saved catalogs never calls a student's tool. */
(function () {
  const M={names:new Map(),reason:'도구 표시 이름을 아직 읽지 않았습니다.',state:'unread',pending:null,readAt:0};
  const korean = value => typeof value==='string' && /[가-힣]/.test(value) ? value.trim().split('\n')[0].slice(0,100) : '';
  function resolve(raw) {
    raw=String(raw||'');
    const key=UI.toolKey(raw), standard=UI.standardToolName(raw);
    if(standard)return {name:standard,raw,reason:'',state:'known'};
    const known=M.names.get(key);
    return known ? {...known,raw,state:'known'} : {name:'',raw,state:M.state === 'loaded' ? 'missing' : M.state,reason:M.reason || '등록 목록에 이 도구의 한글 표시 이름이 없습니다.'};
  }
  async function load(force=false) {
    if(M.pending)return M.pending;
    if(!force && M.readAt && Date.now()-M.readAt<30000)return;
    M.pending=(async()=>{
      M.state='loading';
      try{
        const base=typeof API!=='undefined'?API.process:'';
        const [options,catalog]=await Promise.all([getJ(base+'/api/agent-authoring/options'),getJ(base+'/api/mcp/selectable')]);
        if(!Array.isArray(options.servers)||!Array.isArray(catalog.servers))throw new Error('이름 목록 응답 형식이 올바르지 않습니다.');
        const servers=new Map(options.servers.map(s=>[s.name,korean(s.description)])), names=new Map();
        for(const server of catalog.servers){
          for(const tool of server.tools||[]){
            const raw=tool.tool_id||`mcp__${server.name}__${tool.name}`;
            const label=korean(tool.title)||korean(tool.description), serverLabel=servers.get(server.name)||'';
            if(label)names.set(raw,{name:[serverLabel,label].filter(Boolean).join(' · '),raw,reason:serverLabel?'':'서버의 한글 표시 이름은 등록되지 않았습니다.'});
          }
        }
        M.names=names;M.reason='';M.state='loaded';
      }catch(e){M.names=new Map();M.state='error';M.reason='도구 표시 이름을 확인하지 못했습니다: '+e.message+' 실제 도구 실행 결과와는 별개입니다.';}
      finally{M.readAt=Date.now();M.pending=null;}
    })();
    return M.pending;
  }
  window.hydToolNames={resolve,load};
})();
