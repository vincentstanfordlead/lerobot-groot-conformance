"""Record docs/img/webapp.gif: home page -> inspect a dataset -> report -> Model Validation preview.

    pip install playwright   # drives the installed Google Chrome (channel="chrome"); no browser download
    .venv/bin/python scripts/record_webapp_gif.py

Serves docs/ from an in-process server on a free port, so it records the working copy. The example is
lerobot/aloha_sim_transfer_cube_human (the home page's "two steps away" example), checked live against
the Hugging Face Hub, so the run needs network. Re-run after UI changes.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
import io, time, json
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
VW,VH,OUTW=1200,750,1000
frames=[]  # (PIL image, ms)
cur=[VW*0.5,VH*0.9]
CURSOR=[(0,0),(0,17),(4.5,13),(7.5,20),(10,19),(7,12),(12.5,12)]
def shot(page,ms,click=False):
    im=Image.open(io.BytesIO(page.screenshot())).convert('RGB')
    s=im.width/VW; d=ImageDraw.Draw(im)
    x,y=cur[0]*s,cur[1]*s
    if click: r=16*s; d.ellipse([x-r,y-r,x+r,y+r],outline=(42,120,214),width=int(3*s))
    pts=[(x+px*1.4*s,y+py*1.4*s) for px,py in CURSOR]
    d.polygon(pts,fill='black',outline='white',width=int(1.5*s))
    frames.append((im.resize((OUTW,int(OUTW*VH/VW)),Image.LANCZOS),ms))
def move(page,sel,steps=8):
    b=page.locator(sel).first.bounding_box(); tx,ty=b['x']+b['width']*0.5,b['y']+b['height']*0.5
    sx,sy=cur
    for i in range(1,steps+1):
        t=i/steps; t=t*t*(3-2*t); cur[0]=sx+(tx-sx)*t; cur[1]=sy+(ty-sy)*t
        page.mouse.move(*cur); shot(page,40)
import threading, functools, http.server
DOCS=str(ROOT / 'docs')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Q,directory=DOCS))
threading.Thread(target=srv.serve_forever,daemon=True).start()
BASE=f'http://127.0.0.1:{srv.server_port}/'
with sync_playwright() as p:
    br=p.chromium.launch(channel='chrome',headless=True)
    page=br.new_page(viewport={'width':VW,'height':VH},device_scale_factor=2,color_scheme='light')
    page.goto(BASE); page.wait_for_timeout(800)
    shot(page,1400)
    move(page,'#heroIn'); page.click('#heroIn'); shot(page,150,True)
    text='lerobot/aloha_sim_transfer_cube_human'
    for i in range(0,len(text),3):
        page.keyboard.type(text[i:i+3]); shot(page,60)
    shot(page,500)
    move(page,'.go-btn'); shot(page,120,True); page.click('.go-btn')
    for _ in range(14): page.wait_for_timeout(150); shot(page,150)
    shot(page,2600)  # read the report
    move(page,'#rX'); shot(page,120,True); page.click('#rX'); page.wait_for_timeout(300); shot(page,500)
    move(page,'#toBuild, [data-sec=validation]'); shot(page,120,True); page.click('#toBuild, [data-sec=validation]'); page.wait_for_timeout(500)
    shot(page,900)
    for y in range(0,61,60):
        page.mouse.wheel(0,60); page.wait_for_timeout(60); shot(page,60)
    move(page,'.pv-banner b',10); cur[0]+=34; cur[1]+=10; page.mouse.move(*cur); shot(page,900)
    shot(page,3000)
    br.close()

OUT=ROOT / 'docs' / 'img' / 'webapp.gif'
ims=[f for f,_ in frames]; ds=[ms for _,ms in frames]
pal=Image.new('RGB',(ims[0].width,ims[0].height*3))
for k,i in enumerate((0,len(ims)//2,len(ims)-1)): pal.paste(ims[i],(0,ims[0].height*k))
pal=pal.quantize(colors=160,method=Image.Quantize.MEDIANCUT)
q=[f.quantize(palette=pal,dither=Image.Dither.NONE) for f in ims]
q[0].save(OUT,save_all=True,append_images=q[1:],duration=ds,loop=0,optimize=True,disposal=1)
print(len(q), 'frames', sum(ds) / 1000, 's', OUT.stat().st_size // 1000, 'kB')
