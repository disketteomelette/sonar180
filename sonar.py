#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse,json,queue,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import serial

L=threading.Lock();dist=[-1]*181;la=None;dr=None;sw=0;ts=0.0
CL=threading.Lock();C=[];D=json.dumps

def bc(o):
  m=D(o,separators=(",",":"))
  with CL:
    dead=[]
    for q in C:
      try:q.put_nowait(m)
      except queue.Full: dead.append(q)
    for q in dead:
      try:C.remove(q)
      except ValueError:pass

def pl(s):
  s=s.strip()
  if ":" not in s:return
  a,d=s.split(":",1)
  try:a=int(a);d=int(d)
  except:return
  if 0<=a<=180:return a,d

def ser(port,baud):
  global la,dr,sw,ts
  ser=None
  while 1:
    try:
      if ser is None:
        ser=serial.Serial(port,baudrate=baud,timeout=1);time.sleep(.2)
        try:ser.reset_input_buffer()
        except:pass
      r=ser.readline()
      if not r:continue
      x=pl(r.decode("utf-8","ignore"))
      if not x:continue
      a,d=x;now=time.time();snap=None
      with L:
        if la is not None:
          nd=1 if a-la>0 else (-1 if a-la<0 else 0)
          if nd and dr is not None and nd!=dr:
            sw+=1; snap={"type":"sweep_snapshot","sweep":sw,"ts":now,"dist":dist.copy()}
          if nd: dr=nd
        dist[a]=d; la=a; ts=now
        pt={"type":"point","angle":a,"dist":d,"sweep":sw,"ts":now}
      bc(pt)
      if snap: bc(snap)
    except serial.SerialException:
      time.sleep(.5)
      try:ser.close()
      except:pass
      ser=None
      try: ser=serial.Serial(port,baudrate=baud,timeout=1);time.sleep(.2); ser.reset_input_buffer()
      except: ser=None; time.sleep(1)
    except: time.sleep(.01)

HTML=r'''<!doctype html><html lang=es><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Sonar180</title>
<style>
html,body{height:100%;margin:0;background:#0b0f14;color:#d7e3f4;font-family:system-ui,Segoe UI,Roboto,Ubuntu,Cantarell,Arial}
#wrap{display:flex;flex-direction:column;height:100%}
#top{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.08);display:flex;flex-direction:column;gap:10px}
#statusRow,#controlsRow{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
#top b{font-weight:650}
.pill{padding:4px 8px;border:1px solid rgba(255,255,255,.14);border-radius:999px;font-size:12px;opacity:.9}
.ctl{display:flex;align-items:center;gap:6px;padding:4px 8px;border:1px solid rgba(255,255,255,.14);border-radius:12px;font-size:12px;opacity:.95}
input[type=number]{width:92px;background:transparent;color:#d7e3f4;border:1px solid rgba(255,255,255,.14);border-radius:8px;padding:4px 6px}
input[type=range]{width:160px}
button{background:transparent;color:#d7e3f4;border:1px solid rgba(255,255,255,.14);border-radius:10px;padding:6px 10px;cursor:pointer}
button:active{transform:translateY(1px)}
#main{flex:1;display:grid;gap:10px;padding:10px 14px;box-sizing:border-box}
@media (min-width:980px){#main{grid-template-columns:1.25fr 1fr;grid-template-rows:1fr}#rightCol{height:100%;display:grid;grid-template-rows:1fr 1fr;gap:10px}}
@media (max-width:979px){#main{grid-template-columns:1fr;grid-template-rows:auto auto auto}#rightCol{display:grid;grid-template-rows:1fr 1fr;gap:10px}}
.card{border:1px solid rgba(255,255,255,.10);border-radius:16px;padding:10px;background:rgba(255,255,255,.02);box-shadow:0 6px 30px rgba(0,0,0,.25);overflow:hidden;display:flex;flex-direction:column;min-height:240px}
.title{font-size:13px;opacity:.85;margin:0 0 6px 0}
canvas{width:100%;flex:1;display:block}
</style></head><body>
<div id=wrap><div id=top>
  <div id=statusRow><b>Sonar180</b>
    <span class=pill>SSE: <span id=sse>conectando</span></span>
    <span class=pill>Sweep: <span id=sweep>0</span></span>
    <span class=pill>Ángulo: <span id=ang>-</span></span>
    <span class=pill>Dist: <span id=dist>-</span> cm</span>
    <span class=pill>FPS: <span id=fps>0</span></span>
    <span class=pill>último dato: <span id=age>-</span>s</span>
  </div>
  <div id=controlsRow>
    <span class=ctl>Max cm <input id=maxcm type=number min=50 max=5000 value=300></span>
    <span class=ctl>Umbral <input id=thr type=number min=10 max=5000 value=80></span>
    <span class=ctl><label><input id=showPoints type=checkbox checked> puntos</label></span>
    <span class=ctl><label><input id=showFill type=checkbox checked> relleno</label></span>
    <span class=ctl><label><input id=showHeat type=checkbox checked> heatmap</label></span>
    <span class=ctl>alpha rell <input id=fillA type=range min=0 max=100 value=22></span>
    <span class=ctl><label><input id=emaOn type=checkbox checked> EMA</label></span>
    <span class=ctl>alpha EMA <input id=emaA type=range min=1 max=100 value=35></span>
    <button id=pauseBtn>Pausar</button><button id=capBtn>Capturar PNG</button>
  </div>
</div>
<div id=main>
  <div class=card id=radarCard><p class=title>Sonar</p><canvas id=radar></canvas></div>
  <div id=rightCol>
    <div class=card><p class=title>Heatmap</p><canvas id=heat></canvas></div>
    <div class=card><p class=title>Escenario 3D radial</p><canvas id=scene></canvas></div>
  </div>
</div></div>
<script>
(()=>{const $=id=>document.getElementById(id),
radarC=$("radar"),heatC=$("heat"),sceneC=$("scene"),
rctx=radarC.getContext("2d",{alpha:false}),hctx=heatC.getContext("2d",{alpha:false}),xctx=sceneC.getContext("2d",{alpha:false}),
elSSE=$("sse"),elSweep=$("sweep"),elAng=$("ang"),elDist=$("dist"),elFPS=$("fps"),elAge=$("age"),
elMaxcm=$("maxcm"),elThr=$("thr"),elShowPoints=$("showPoints"),elShowFill=$("showFill"),elShowHeat=$("showHeat"),
elFillA=$("fillA"),elEmaOn=$("emaOn"),elEmaA=$("emaA"),pauseBtn=$("pauseBtn"),capBtn=$("capBtn"),
dist=new Array(181).fill(-1),ema=new Array(181).fill(-1);
let lastAngle=0,sweep=0,lastTS=0,paused=false,fpsC=0;const HR=4,cl=(v,a,b)=>v<a?a:v>b?b:v;
setInterval(()=>{elFPS.textContent=fpsC;fpsC=0},1000);
const maxCM=()=>{let v=parseInt(elMaxcm.value||300,10);return isFinite(v)&&v>0?v:300},
thrCM=()=>{let v=parseInt(elThr.value||80,10);return isFinite(v)&&v>0?v:80},
fillA=()=>cl(parseInt(elFillA.value||22,10),0,100)/100,
emaA=()=>cl(parseInt(elEmaA.value||35,10),1,100)/100,
angR=a=>Math.PI-a*Math.PI/180;
const colR=(d,mc)=>{let t=cl(d/mc,0,1),r,g,b;if(t<.5){let u=t/.5;r=255;g=Math.round(90+165*u);b=60}else{let u=(t-.5)/.5;r=Math.round(255-180*u);g=255;b=Math.round(60+150*u)}return`rgb(${r},${g},${b})`};
const ST=[[0,255,40,40],[.18,255,140,40],[.33,255,235,70],[.5,60,255,110],[.67,60,220,255],[.82,70,120,255],[1,170,70,255]];
const col3=(d,mc)=>{let t=cl(d/mc,0,1);for(let i=0;i<ST.length-1;i++){let a=ST[i],b=ST[i+1];if(t>=a[0]&&t<=b[0]){let u=(t-a[0])/(b[0]-a[0]||1),r=Math.round(a[1]+(b[1]-a[1])*u),g=Math.round(a[2]+(b[2]-a[2])*u),bl=Math.round(a[3]+(b[3]-a[3])*u);return`rgb(${r},${g},${bl})`}}let z=ST[ST.length-1];return`rgb(${z[1]},${z[2]},${z[3]})`};
function fit(c,ctx){let r=c.getBoundingClientRect(),d=window.devicePixelRatio||1,w=Math.max(1,r.width*d|0),h=Math.max(1,r.height*d|0);if(c.width!==w||c.height!==h){c.width=w;c.height=h;ctx.imageSmoothingEnabled=true}}
function drawRadar(){
  fit(radarC,rctx);let W=radarC.width,H=radarC.height,cx=W/2,cy=H*.985,Rx=W*.49,Ry=H*.92;
  rctx.fillStyle="#0b0f14";rctx.fillRect(0,0,W,H);
  rctx.strokeStyle="rgba(120,220,140,.16)";rctx.lineWidth=Math.max(1,((W+H)/1400)|0);
  for(let t of [.25,.5,.75,1]){rctx.beginPath();rctx.ellipse(cx,cy,Rx*t,Ry*t,0,Math.PI,0,false);rctx.stroke()}
  rctx.beginPath();rctx.moveTo(cx-Rx,cy);rctx.lineTo(cx+Rx,cy);rctx.stroke();
  for(let a=0;a<=180;a+=30){let r=angR(a);rctx.beginPath();rctx.moveTo(cx,cy);rctx.lineTo(cx+Math.cos(r)*Rx,cy-Math.sin(r)*Ry);rctx.stroke()}
  rctx.fillStyle="rgba(215,227,244,.7)";rctx.font=`${Math.max(14,((W+H)/220)|0)}px system-ui,sans-serif`;
  rctx.fillText("0°",cx-Rx+10,cy-10);rctx.fillText("180°",cx+Rx-70,cy-10);rctx.fillText("90°",cx-18,cy-Ry+24);
  let mc=maxCM(),thr=thrCM(),src=elEmaOn.checked?ema:dist;
  if(elShowFill.checked){
    let pts=[],md=1/0;
    for(let a=0;a<=180;a++){let d=src[a];if(d<0)continue;let dd=Math.min(d,mc),t=dd/mc,r=angR(a),x=cx+Math.cos(r)*(t*Rx),y=cy-Math.sin(r)*(t*Ry);pts.push([x,y,d]);if(d<md)md=d}
    if(pts.length>=3){
      rctx.beginPath();rctx.moveTo(cx,cy);for(let p of pts)rctx.lineTo(p[0],p[1]);rctx.lineTo(cx,cy);rctx.closePath();
      if(!isFinite(md))md=mc;
      rctx.fillStyle=colR(md,mc).replace("rgb","rgba").replace(")",`,`+fillA()+`)`);rctx.fill()
    }
  }
  if(elShowPoints.checked){
    let pr=Math.max(2.2,((W+H)/900)|0);
    for(let a=0;a<=180;a++){
      let d=src[a];if(d<0)continue;let dd=Math.min(d,mc),t=dd/mc,r=angR(a),x=cx+Math.cos(r)*(t*Rx),y=cy-Math.sin(r)*(t*Ry);
      rctx.fillStyle=colR(d,mc);rctx.beginPath();rctx.arc(x,y,pr,0,Math.PI*2);rctx.fill();
      if(d<=thr){rctx.strokeStyle="rgba(255,60,60,.70)";rctx.lineWidth=Math.max(1.5,pr*.75);rctx.beginPath();rctx.arc(x,y,pr*2.2,0,Math.PI*2);rctx.stroke()}
    }
  }
  rctx.strokeStyle="rgba(180,255,210,.45)";rctx.lineWidth=Math.max(2,((W+H)/700)|0);
  let r=angR(lastAngle);rctx.beginPath();rctx.moveTo(cx,cy);rctx.lineTo(cx+Math.cos(r)*Rx,cy-Math.sin(r)*Ry);rctx.stroke()
}
const heatCol=(d,mc)=>d<0?"rgb(11,15,20)":`rgb(${(255*(1-cl(d/mc,0,1)))|0},${(255*cl(d/mc,0,1))|0},60)`;
function heatGrid(){fit(heatC,hctx);let W=heatC.width,H=heatC.height;hctx.fillStyle="rgb(11,15,20)";hctx.fillRect(0,0,W,H);
  hctx.strokeStyle="rgba(255,255,255,.06)";hctx.lineWidth=1;
  for(let a=0;a<=180;a+=30){let x=((a/180)*(W-1))|0;hctx.beginPath();hctx.moveTo(x,0);hctx.lineTo(x,H);hctx.stroke()}
}
function heatShift(){let W=heatC.width,H=heatC.height,dy=HR;hctx.drawImage(heatC,0,0,W,H-dy,0,dy,W,H-dy);hctx.fillStyle="rgb(11,15,20)";hctx.fillRect(0,0,W,dy)}
function heatRow(arr){if(!elShowHeat.checked)return;let W=heatC.width,mc=maxCM();for(let x=0;x<W;x++){let a=((x/(W-1))*180+.5)|0;hctx.fillStyle=heatCol(arr[a],mc);hctx.fillRect(x,0,1,HR)}}
function draw3D(){
  fit(sceneC,xctx);let W=sceneC.width,H=sceneC.height; xctx.fillStyle="#070a0f";xctx.fillRect(0,0,W,H);
  let mc=maxCM(),thr=thrCM(),src=elEmaOn.checked?ema:dist,cx=W/2,cy=H*.985,R=Math.min(W*.49,H*.92);
  xctx.strokeStyle="rgba(255,255,255,.06)";xctx.lineWidth=1;
  for(let t of [.25,.5,.75,1]){xctx.beginPath();xctx.arc(cx,cy,R*t,Math.PI,0,false);xctx.stroke()}
  for(let a=0;a<=180;a+=30){let r=angR(a);xctx.beginPath();xctx.moveTo(cx,cy);xctx.lineTo(cx+Math.cos(r)*R,cy-Math.sin(r)*R);xctx.stroke()}
  let bars=[];
  for(let a=0;a<=180;a++){let d=src[a];if(d<0)continue;let t=cl(d/mc,0,1),rr=t*R,r=angR(a),x=cx+Math.cos(r)*rr,y=cy-Math.sin(r)*rr,s=1-t,w=1.5+s*8,h=10+s*(H*.32);bars.push([t,d,x,y,w,h])}
  bars.sort((p,q)=>q[0]-p[0]);
  for(let b of bars){
    let t=b[0],d=b[1],x=b[2],y=b[3],w=b[4],h=b[5],a=.16+(1-t)*.78,col=col3(d,mc).replace("rgb","rgba").replace(")",`,`+a+`)`);
    xctx.fillStyle="rgba(0,0,0,.22)";xctx.fillRect(x-w/2+1.5,y-h+2.5,w,h);
    xctx.fillStyle=col;xctx.fillRect(x-w/2,y-h,w,h);
    if(d<=thr){xctx.strokeStyle="rgba(255,60,60,.85)";xctx.lineWidth=1.4;xctx.strokeRect(x-w/2-.5,y-h-.5,w+1,h+1)}
  }
  xctx.strokeStyle="rgba(200,255,225,.28)";xctx.lineWidth=Math.max(2,((W+H)/900)|0);
  let r=angR(lastAngle);xctx.beginPath();xctx.moveTo(cx,cy);xctx.lineTo(cx+Math.cos(r)*R,cy-Math.sin(r)*R);xctx.stroke();
  xctx.fillStyle="rgba(215,227,244,.65)";xctx.font=`${Math.max(12,((W+H)/260)|0)}px system-ui,sans-serif`;
  xctx.fillText("cerca",10,cy-12);xctx.fillText("lejos",10,cy-R+18)
}
const emaApply=(i,d)=>{let a=emaA(),p=ema[i]; if(d<0)return; ema[i]=p<0?d:a*d+(1-a)*p};
pauseBtn.onclick=()=>{paused=!paused;pauseBtn.textContent=paused?"Reanudar":"Pausar"};
capBtn.onclick=()=>{let u=radarC.toDataURL("image/png"),a=document.createElement("a");a.href=u;a.download=`radar_sweep_${sweep}.png`;document.body.appendChild(a);a.click();a.remove()};
function tick(){if(lastTS)elAge.textContent=(Date.now()/1000-lastTS).toFixed(1);drawRadar();draw3D();requestAnimationFrame(tick)}
function sse(){
  const es=new EventSource("/events");
  es.onopen=()=>elSSE.textContent="OK";
  es.onerror=()=>elSSE.textContent="ERROR";
  es.onmessage=ev=>{
    let m;try{m=JSON.parse(ev.data)}catch{return}
    if(!m||paused)return;
    if(m.type==="snapshot"){
      sweep=m.sweep|0;lastAngle=m.last_angle|0;lastTS=m.ts||Date.now()/1000;
      if(Array.isArray(m.dist)&&m.dist.length>=181)for(let i=0;i<=180;i++){dist[i]=m.dist[i]|0;ema[i]=dist[i]>=0?dist[i]:-1}
      elSweep.textContent=sweep;elAng.textContent=lastAngle;elDist.textContent=dist[lastAngle]??-1;heatGrid();return
    }
    if(m.type==="point"){
      fpsC++;let a=m.angle|0,d=m.dist|0;
      if(a>=0&&a<=180){dist[a]=d; if(elEmaOn.checked)emaApply(a,d); lastAngle=a}
      sweep=m.sweep|0;lastTS=m.ts||Date.now()/1000;
      elSweep.textContent=sweep;elAng.textContent=a;elDist.textContent=d;return
    }
    if(m.type==="sweep_snapshot"){
      if(!Array.isArray(m.dist)||m.dist.length<181)return;
      if(elShowHeat.checked){fit(heatC,hctx);heatShift();heatRow(m.dist)}
    }
  }
}
heatGrid();sse();addEventListener("resize",heatGrid);tick();
})();
</script></body></html>'''

class H(BaseHTTPRequestHandler):
  def log_message(self,*a): pass
  def do_GET(self):
    p=self.path
    if p=="/" or p.startswith("/index"):
      b=HTML.encode();self.send_response(200)
      self.send_header("Content-Type","text/html; charset=utf-8")
      self.send_header("Content-Length",str(len(b)))
      self.end_headers();self.wfile.write(b);return
    if p.startswith("/events"):
      self.send_response(200)
      self.send_header("Content-Type","text/event-stream")
      self.send_header("Cache-Control","no-cache")
      self.send_header("Connection","keep-alive")
      self.end_headers()
      q=queue.Queue(maxsize=600)
      with CL: C.append(q)
      with L: snap={"type":"snapshot","sweep":sw,"last_angle":la or 0,"dist":dist,"ts":ts}
      try:
        self.wfile.write(("data: "+D(snap,separators=(",",":"))+"\n\n").encode()); self.wfile.flush()
      except:
        with CL:
          if q in C: C.remove(q)
        return
      try:
        while 1:
          try:
            m=q.get(timeout=15)
            self.wfile.write(("data: "+m+"\n\n").encode()); self.wfile.flush()
          except queue.Empty:
            self.wfile.write(b": ping\n\n"); self.wfile.flush()
      except: pass
      finally:
        with CL:
          if q in C: C.remove(q)
      return
    self.send_response(404); self.end_headers(); self.wfile.write(b"404")

def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("--port",required=True)
  ap.add_argument("--baud",type=int,default=115200)
  ap.add_argument("--http",type=int,default=8000)
  a=ap.parse_args()
  threading.Thread(target=ser,args=(a.port,a.baud),daemon=True).start()
  print(f"HTTP: http://127.0.0.1:{a.http}   (serie: {a.port} @ {a.baud})")
  ThreadingHTTPServer(("0.0.0.0",a.http),H).serve_forever()

if __name__=="__main__": main()
