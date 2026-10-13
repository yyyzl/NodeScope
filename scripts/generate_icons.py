"""由已确认原型的罗盘标记生成桌面图标。仅开发时需要 Pillow。"""
from pathlib import Path
from PIL import Image, ImageDraw

root=Path(__file__).resolve().parents[1]
image=Image.new('RGBA',(1024,1024),(0,0,0,0))
draw=ImageDraw.Draw(image)
draw.rounded_rectangle((28,28,996,996),radius=218,fill='#FEFCF6')
draw.ellipse((212,212,812,812),outline='#2472C2',width=40)
draw.polygon([(322,706),(706,322),(575,575)],fill='#2472C2')
draw.polygon([(322,706),(448,448),(706,322)],fill='#9FC5EA')
draw.ellipse((710,213,818,321),fill='#F4D758')
windows=root/'desktop/windows/runner/resources/app_icon.ico'
image.save(windows,format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
mac=root/'desktop/macos/Runner/Assets.xcassets/AppIcon.appiconset'
for size in [16,32,64,128,256,512,1024]:
    image.resize((size,size),Image.Resampling.LANCZOS).save(mac/('app_icon_'+str(size)+'.png'))
print('已生成与原型一致的罗盘图标')
