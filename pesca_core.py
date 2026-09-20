"""Analisi Pesca sperimentale. Non contiene funzioni di input/mouse."""
import re

class CicloPesca:
    def __init__(self):
        self.reset()
    def reset(self):
        self.armed=True; self.sent_at=None; self.normal_seen=False
        self.baseline=None; self.hits=None; self.simulated=0
        self.state='ATTESA FINESTRA'; self.last_point=None
    def update(self, now, present, color, point, hits):
        if not present:
            self.reset(); return None
        if hits is not None: self.hits=hits
        if self.hits==3:
            self.state='COMPLETATO 3/3'; return None
        if not self.armed:
            if color=='NORMAL': self.normal_seen=True
            # Il contatore misura i successi, non autorizza la ripresa dopo un miss.
            if self.normal_seen and now-self.sent_at>=2 and hits is not None:
                self.armed=True
            else:
                self.state='ATTESA COOLDOWN / NUOVO ROSSO'; return None
        if hits is None:
            self.state='ATTESA LETTURA CONTATORE'; return None
        if color=='RED' and point is not None:
            self.armed=False; self.sent_at=now; self.normal_seen=False
            self.baseline=self.hits; self.simulated+=1; self.last_point=point
            self.state='CLICK SIMULATO - nessun input inviato'
            return point
        self.state='PESCE NON RILEVATO' if point is None else 'TRACKING / ATTESA ROSSO'
        return None


def leggi_colpi(results):
    for row in results:
        text, confidence=row[1],float(row[2])
        m=re.fullmatch(r'([0-3])/3',re.sub(r'\s+','',text))
        if m and confidence>=0.55:return int(m.group(1))
    return None

class ContatoreVisivo:
    """Quattro cifre del tema osservato, con rifiuto delle letture ambigue."""
    def __init__(self, path):
        import json, numpy as np
        data=json.loads(path.read_text(encoding='utf-8'))
        self.templates=[np.asarray(t,dtype=np.uint8) for t in data['templates']]
        if len(self.templates)!=4 or any(t.shape!=(13,11) for t in self.templates):
            raise ValueError('Riferimenti contatore non validi')
    def read(self, gray):
        import cv2
        patch=gray[41:54,243:254]
        scores=[float(cv2.matchTemplate(patch,t,cv2.TM_CCOEFF_NORMED)[0,0]) for t in self.templates]
        ranked=sorted(range(4),key=lambda i:scores[i],reverse=True)
        best,second=ranked[:2]
        value=best if scores[best]>=0.90 and scores[best]-scores[second]>=0.08 else None
        return value,scores[best]

class VisionePesca:
    def __init__(self, reference):
        import cv2, numpy as np
        self.cv=cv2; self.np=np
        self.ref=cv2.imread(str(reference))
        if self.ref is None:raise ValueError('Manca pesca_riferimento.png')
        from pathlib import Path
        self.counter=ContatoreVisivo(Path(reference).with_name('pesca_contatore.json'))
        self.header=self.ref[2:29,2:282]
        self.headergray=cv2.cvtColor(self.header,cv2.COLOR_BGR2GRAY)
    def find_window(self, image):
        cv=self.cv; best=None
        gray=cv.cvtColor(image,cv.COLOR_BGR2GRAY)
        for scale in (0.75,1,1.25,1.5,1.75,2):
            tpl=cv.resize(self.headergray,None,fx=scale,fy=scale)
            if tpl.shape[0]>gray.shape[0] or tpl.shape[1]>gray.shape[1]:continue
            _,score,_,loc=cv.minMaxLoc(cv.matchTemplate(gray,tpl,cv.TM_CCOEFF_NORMED))
            x,y=round(loc[0]-2*scale),round(loc[1]-2*scale)
            w,h=round(285*scale),round(258*scale)
            if x<0 or y<0 or x+w>gray.shape[1] or y+h>gray.shape[0]:continue
            if best is None or score>best[0]:best=(score,(x,y,w,h))
        return best[1] if best and best[0]>=0.78 else None
    def analyse(self, crop):
        cv,np=self.cv,self.np
        im=cv.resize(crop,(285,258));gray=cv.cvtColor(im,cv.COLOR_BGR2GRAY)
        header_score=cv.matchTemplate(gray[2:29,2:282],self.headergray,cv.TM_CCOEFF_NORMED)[0,0]
        if header_score<0.72:return None
        hsv=cv.cvtColor(im,cv.COLOR_BGR2HSV);h,s,v=cv.split(hsv)
        yy,xx=np.ogrid[:258,:285];radius=np.sqrt((xx-144)**2+(yy-141)**2)
        annulus=(radius>=60)&(radius<=66)
        red=(((h<12)|(h>165))&(s>40)&(v>130)&annulus).sum()/annulus.sum()
        normal=((((h>=15)&(h<=40))|(s<60))&(v>170)&annulus).sum()/annulus.sum()
        color='RED' if red>=0.10 else ('NORMAL' if normal>=0.10 else 'UNKNOWN')
        # Sagoma blu-grigia: indipendente dalla rotazione, separata dall'acqua.
        # Le soglie sono calibrate sui frame ricevuti, non universali per altre skin.
        blue,green,red_channel=cv.split(im.astype(np.int16))
        mask=((blue>75)&(blue<170)&(green>40)&(green<145)&
              (red_channel>25)&(red_channel<135)&(blue-red_channel<90)&(blue>=green)).astype('uint8')
        allowed=np.zeros((258,285),np.uint8);allowed[44:240,22:268]=1
        allowed[:65,207:]=0  # contatore: non e' un bersaglio
        allowed[228:,39:258]=0  # barra tempo
        allowed[(xx-47)**2+(yy-235)**2<=14**2]=0  # orologio
        mask &= allowed
        _,labels,stats,centers=cv.connectedComponentsWithStats(mask)
        candidates=[]
        inner=cv.erode(allowed,np.ones((3,3),np.uint8))
        for label,(stat,center) in enumerate(zip(stats[1:],centers[1:]),1):
            x,y,w,h,area=map(int,stat)
            if not (40<=area<=600 and 6<=w<=40 and 6<=h<=40):continue
            fill=area/(w*h)
            if not 0.25<=fill<=0.90:continue
            component=labels==label
            clipped=bool(np.any(component & (inner==0)))
            # Il punto scelto resta dentro la sagoma, anche se concava.
            ys,xs=np.where(component)
            closest=np.argmin((xs-center[0])**2+(ys-center[1])**2)
            point=(float(xs[closest]),float(ys[closest]))
            quality=min(1.0,area/140)*min(1.0,fill/0.55)
            candidates.append((quality,point,(x,y,w,h),clipped))
        point=None;box=None;score=0.0;reason='Nessuna sagoma affidabile'
        if len(candidates)==1:
            score,candidate,box,clipped=candidates[0]
            if clipped:reason='Sagoma parziale vicino all’interfaccia: punto non confermato'
            elif score<0.65:reason='Sagoma troppo debole: punto non confermato'
            else:point=candidate;reason='Sagoma confermata'
        elif len(candidates)>1:
            reason='Piu sagome possibili: punto non confermato'
        counter_value,counter_score=self.counter.read(gray)
        return dict(counter_value=counter_value,counter_score=counter_score,color=color,red_ratio=float(red),confidence=float(score),point=point,
                    fish_box=box,reason=reason,image=im)
