const fs=require('fs'),cp=require('child_process');const path=require('path');if(!process.argv[2])throw Error('Usage: node encode.cjs OUTPUT_DIR [FFMPEG]');const root=path.resolve(process.argv[2]);
const {frames,duration}=JSON.parse(fs.readFileSync(root+'/smooth-timing.json','utf8'));
if(!frames.length)throw Error('No captured frames');const first=frames[0].sourceTimestamp;const time=f=>(f.sourceTimestamp-first)*1000;
let list='';for(let i=0;i<frames.length;i++){list+=`file '${frames[i].file}'\nduration ${Math.max(.001,((frames[i+1]?time(frames[i+1]):duration)-time(frames[i]))/1000)}\n`;}
list+=`file '${frames.at(-1).file}'\n`;fs.writeFileSync(root+'/smooth.concat',list);
const ff=process.argv[3]||'ffmpeg';
const output=root+'/arrows-ego-smooth-test.mp4';
cp.execFileSync(ff,['-y','-f','concat','-safe','0','-i',root+'/smooth.concat','-vf','scale=1280:800:force_original_aspect_ratio=decrease,pad=1280:800:(ow-iw)/2:(oh-ih)/2,setsar=1','-r','30','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',output],{stdio:'pipe'});
cp.execFileSync(ff,['-v','error','-i',output,'-f','null','-'],{stdio:'pipe'});
const clicks=JSON.parse(fs.readFileSync(root+'/smooth-clicks.json','utf8'));
const timing=JSON.parse(fs.readFileSync(root+'/smooth-timing.json','utf8'));const ts=frames.map(f=>(f.sourceTimestamp-frames[0].sourceTimestamp)*1000);const moves=timing.actions.filter(a=>a.end).map(a=>{const values=ts.filter(t=>t>=a.time&&t<=a.end);return {durationMs:a.end-a.time,frames:values.length,maxGapMs:Math.max(0,...values.slice(1).map((t,i)=>t-values[i]))};});
const errors=clicks.map(c=>Math.hypot(c.x-c.pointerX,c.y-c.pointerY));
fs.writeFileSync(root+'/report.json',JSON.stringify({date:new Date().toISOString(),durationMs:duration,sourceFrames:frames.length,moves,clicks:clicks.length,maxClickAlignmentErrorCssPixels:errors.length?Math.max(...errors):null,capture:'CDP screencast; source timestamps; no speedup or post-production cursor animation',pointer:'White arrow DOM overlay follows real mousemove events, pointer-events:none; removed after recording',typing:'Korean complete syllables via insertText, variable inter-character delays; not Korean IME jamo composition',foregroundActions:0,claudeActions:0,audio:'none',verification:'full ffmpeg decode passed',limitations:['Short test only; not 50-minute stability verification','Capture updates on rendered changes; encoded 30fps does not mean 30 distinct source frames/sec']},null,2));
console.log({output,durationMs:duration,clicks:clicks.length,maxError:Math.max(...errors),decode:'passed'});
