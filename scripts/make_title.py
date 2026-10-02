"""Render the README title (docs/img/title_light.png, title_dark.png) in the web app's heading font.

    pip install playwright   # drives the installed Google Chrome; needs network for the Google Font
    .venv/bin/python scripts/make_title.py

GitHub strips colour from README text, so the highlighted word is an image. Light: yellow highlighter
under "smog", as on the app's home page. Dark: "smog" in yellow. The README picks one with <picture>.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=str(Path(__file__).resolve().parent.parent / 'docs' / 'img') + '/'
T='Does your robot data pass the <em>smog</em> check?'
CSS={'light':"h1{color:#1b1b1b} em{background:linear-gradient(transparent 62%,#FFCF00 62% 92%,transparent 92%)}",
     'dark':"h1{color:#e6edf3} em{color:#FFCF00}"}
with sync_playwright() as p:
    br=p.chromium.launch(channel='chrome',headless=True)
    pg=br.new_page(device_scale_factor=2,viewport={'width':1200,'height':200})
    for mode,css in CSS.items():
        pg.set_content(f"""<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&display=swap" rel="stylesheet">
<style>html,body{{margin:0;background:transparent}} h1{{display:inline-block;font:700 48px/1.15 'Space Grotesk';letter-spacing:-.03em;margin:0;padding:4px 2px 8px}} em{{font-style:normal}} {css}</style><h1>{T}</h1>""")
        pg.wait_for_function("document.fonts.ready.then(()=>document.fonts.check('700 48px \"Space Grotesk\"'))")
        pg.locator('h1').screenshot(path=OUT+f'title_{mode}.png',omit_background=True)
    br.close()
