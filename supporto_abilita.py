"""Calibrated slot observations; no OCR, input APIs or catalogue of icons."""
import math
import numpy as np
from PIL import Image


def validate_skill_visual(skill):
    mode=skill.get('mode','timer')
    if mode not in ('timer','target'):raise ValueError('Modalità abilità non valida.')
    retry=float(str(skill.get('retry',.5)).replace(',','.'))
    if not math.isfinite(retry) or not .2<=retry<=10:raise ValueError('Pausa tentativi: da 0.2 a 10 secondi.')
    calibration=skill.get('calibration')
    if calibration is not None:
        if not isinstance(calibration,dict):raise ValueError('Calibrazione slot non valida.')
        roi=calibration.get('roi');size=calibration.get('window_size');ref=calibration.get('reference')
        if not isinstance(roi,list) or len(roi)!=4 or any(type(v)!=int or v<0 for v in roi):raise ValueError('ROI slot non valida.')
        x,y,w,h=roi
        if not 12<=w<=256 or not 12<=h<=256 or not .5<=w/h<=2:raise ValueError('Seleziona una sola icona, senza cornice o numero tasto.')
        if not isinstance(size,list) or len(size)!=2 or any(type(v)!=int or v<=0 for v in size) or x+w>size[0] or y+h>size[1]:raise ValueError('Slot fuori dalla finestra.')
        if not isinstance(ref,list) or len(ref)!=24*24*3 or any(type(v)!=int or not 0<=v<=255 for v in ref):raise ValueError('Riferimento icona non valido.')
    return dict(mode=mode,retry=retry,calibration=calibration)


def calibrate_slot(image,roi,window_size):
    thumb=np.asarray(image.convert('RGB').resize((24,24),Image.Resampling.BILINEAR))
    if thumb.std()<12 or thumb.mean()<20:raise ValueError('Icona poco leggibile: calibra quando è pronta e senza cursore sopra.')
    c=dict(roi=list(roi),window_size=list(window_size),reference=thumb.flatten().tolist())
    return validate_skill_visual({'calibration':c})['calibration']


def classify_slot(image,calibration):
    now=np.asarray(image.convert('RGB').resize((24,24),Image.Resampling.BILINEAR),dtype=float)
    ref=np.asarray(calibration['reference'],dtype=float).reshape(24,24,3)
    # Exclude border, key labels and skill-level text at the extremes of the crop.
    now=now[3:20,3:21];ref=ref[3:20,3:21]
    lum=now.mean(2);base=ref.mean(2);valid=base>35
    if valid.sum()<40:return dict(state='UNKNOWN',confidence=0.,reason='Riferimento troppo scuro.')
    error=float(np.mean(np.abs(now-ref))/255)
    ratio=lum[valid]/np.maximum(base[valid],1)
    dark=float(np.mean(ratio<.76));bright=float(np.mean(ratio>1.3))
    # A flash alone never confirms activation. Only a sustained dark overlay does.
    chroma=np.mean(np.abs(now/(lum[:,:,None]+15)-ref/(base[:,:,None]+15)))
    if error<.075 and dark<.12 and bright<.12:
        return dict(state='READY',confidence=round(max(0,1-error/.15),2),reason='Simile al riferimento pronto.')
    if dark>=.22 and bright<.10 and .18<float(np.median(ratio))<1.04 and chroma<.22:
        return dict(state='COOLDOWN',confidence=round(min(1,dark+.35),2),reason='Oscuramento compatibile con ricarica.')
    return dict(state='UNKNOWN',confidence=0.,reason='Lampo, icona diversa o lettura ambigua.')


class SkillMonitor:
    def __init__(self,skills):self.skills=skills
    def read(self,capture,area):
        readings={}
        for i,s in enumerate(self.skills):
            if not s['enabled'] or s.get('mode')!='target':continue
            c=s.get('calibration')
            result=dict(state='UNKNOWN',confidence=0.,reason='Calibra lo slot con abilità pronta.')
            if c:
                if list(c['window_size'])!=[area['width'],area['height']]:
                    result['reason']='Dimensioni cambiate: ricalibra lo slot.'
                else:
                    x,y,w,h=c['roi'];roi=dict(left=area['left']+x,top=area['top']+y,width=w,height=h)
                    if any(roi['left']>=m['left'] and roi['top']>=m['top'] and roi['left']+w<=m['left']+m['width'] and roi['top']+h<=m['top']+m['height'] for m in capture.monitors[1:]):
                        try:
                            shot=capture.grab(roi);result=classify_slot(Image.frombytes('RGB',shot.size,shot.rgb),c)
                        except Exception as exc:result['reason']='Cattura slot: '+str(exc)
                    else:result['reason']='Slot fuori dal monitor.'
            readings[i]=result
        return readings


class TargetState:
    def __init__(self):
        self.deadline=0.;self.pending=None;self.last_attempt=-math.inf
        self.ready_count=0;self.dark_count=0;self.dark_since=None
        self.visual='UNKNOWN';self.label='ATTESA LETTURA';self.confirmations=0
    def pause(self):
        self.pending=None;self.ready_count=0;self.dark_count=0;self.dark_since=None;self.visual='UNKNOWN'
    def observe(self,now,reading,interval):
        self.visual=reading.get('state','UNKNOWN');confirmed=False
        self.ready_count=self.ready_count+1 if self.visual=='READY' else 0
        if self.visual=='COOLDOWN' and self.pending is not None and now-self.pending<=2:
            if self.dark_since is None:self.dark_since=now
            self.dark_count+=1
            if self.dark_count>=3 and now-self.dark_since>=.12:
                self.deadline=now+interval;self.pending=None;self.confirmations+=1;confirmed=True
        else:self.dark_count=0;self.dark_since=None
        if self.pending is not None and now-self.pending>2:self.pending=None
        if now<self.deadline:self.label='INTERVALLO'
        elif self.visual=='UNKNOWN':self.label='LETTURA INCERTA'
        elif self.visual=='COOLDOWN':self.label='ATTESA ICONA PRONTA'
        elif self.pending is not None:self.label='TENTATIVI — NON CONFERMATA'
        else:self.label='PRONTA / ATTESA TURNO'
        return confirmed
    def due(self,now,retry):
        return now>=self.deadline and self.ready_count>=2 and now-self.last_attempt>=retry
    def attempt(self,now):
        self.last_attempt=now;self.pending=now;self.dark_count=0;self.dark_since=None
        self.label='ATTESA CONFERMA'
