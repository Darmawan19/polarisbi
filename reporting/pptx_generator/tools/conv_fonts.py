from fontTools.ttLib import TTFont
import os
out="tools/fonts"; os.makedirs(out, exist_ok=True); n=0
for fam in ["poppins","inter"]:
    for w in ["400","500","600","700"]:
        src=f"node_modules/@fontsource/{fam}/files/{fam}-latin-{w}-normal.woff2"
        if os.path.exists(src):
            f=TTFont(src); f.flavor=None; f.save(f"{out}/{fam}-{w}.ttf"); n+=1
print("converted", n)
