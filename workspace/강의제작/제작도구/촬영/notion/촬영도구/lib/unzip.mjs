// 내보내기 zip 풀기(녹화 밖 — v12 27단계 뒷구간의 준비에서). 중앙 디렉터리를 읽어 저장(0) · deflate(8) 항목만 풀고,
// 그 밖의 방식 · 암호 · zip64 · 폴더 밖으로 나가는 이름은 그 항목 이름을 대고 멈춘다. 안에 zip만 들어 있으면(Notion의 Part-N.zip) 그것도 푼다.
export async function unzip(file,dir){
 const fs=await import('node:fs/promises'),zlib=await import('node:zlib'),path=await import('node:path');
 const b=await fs.readFile(file);
 let e=b.length-22;while(e>=0&&b.readUInt32LE(e)!==0x06054b50)e--;
 if(e<0)throw Error('zip end record missing: '+file);
 const n=b.readUInt16LE(e+10);let o=b.readUInt32LE(e+16);const out=[],root=path.resolve(dir);
 const utf8=new TextDecoder('utf-8',{fatal:true});
 for(let i=0;i<n;i++){
  if(b.readUInt32LE(o)!==0x02014b50)throw Error('zip central header broken at '+o+': '+file);
  const flag=b.readUInt16LE(o+8),method=b.readUInt16LE(o+10),csize=b.readUInt32LE(o+20),nl=b.readUInt16LE(o+28),xl=b.readUInt16LE(o+30),cl=b.readUInt16LE(o+32),lo=b.readUInt32LE(o+42);
  let name;try{name=utf8.decode(b.subarray(o+46,o+46+nl));}catch{throw Error('zip entry name is not UTF-8 (flag '+flag+') at '+o+': '+file);}
  o+=46+nl+xl+cl;
  if(flag&1)throw Error('zip entry encrypted: '+name);
  if(csize===0xffffffff||lo===0xffffffff)throw Error('zip64 entry not supported: '+name);
  const target=path.resolve(root,name);
  if(target!==root&&!target.startsWith(root+path.sep))throw Error('zip entry escapes the folder: '+name);
  if(name.endsWith('/')){await fs.mkdir(target,{recursive:true});continue;}
  const lnl=b.readUInt16LE(lo+26),lxl=b.readUInt16LE(lo+28),data=b.subarray(lo+30+lnl+lxl,lo+30+lnl+lxl+csize);
  if(method!==0&&method!==8)throw Error('zip method '+method+' not supported: '+name);
  await fs.mkdir(path.dirname(target),{recursive:true});
  await fs.writeFile(target,method===0?data:zlib.inflateRawSync(data));out.push(target);
 }
 if(out.length&&out.every(f=>f.toLowerCase().endsWith('.zip'))){const inner=[];for(const f of out)inner.push(...await unzip(f,dir));return inner;}
 return out;
}
