"""Optional mana settings, capture and HP > MP > skills arbitration."""
from supporto_core import defaults,validate,SupportEngine,HPFilter,analyze_hp


def validate_mana(data=None):
    if data is None:data={}
    if not isinstance(data,dict):raise ValueError('Configurazione mana non valida.')
    base=dict(enabled=False,threshold=40.0,rearm=60.0,heal_key='F1',uses=1,
              burst_interval=.2,cooldown=2.0,roi=None,window_size=None,color=None)
    base.update({k:v for k,v in data.items() if k in base})
    if not isinstance(base['enabled'],bool):raise ValueError('Auto Mana deve essere ON oppure OFF.')
    probe=defaults();probe.update(base)
    try:checked=validate(probe,resource_only=True)
    except ValueError as exc:raise ValueError('Mana: '+str(exc)) from exc
    return {key:checked[key] for key in base if key in checked}


class SupportCoordinator:
    def __init__(self,config):
        self.config=validate(config)
        self.hp=SupportEngine(self.config)
        m=defaults();m.update(self.config['mana'],auto_heal=self.config['mana']['enabled'],
                             dry_run=self.config['dry_run'])
        self.mp=SupportEngine(m);self.next_input=0
    @property
    def state(self):return self.hp.state
    @property
    def mana_state(self):return self.mp.state if self.config['mana']['enabled'] else 'OFF'
    def suspend(self,now):
        return self.hp.suspend(now)+['Mana: '+x for x in self.mp.suspend(now)]
    def countdowns(self,now):return self.hp.countdowns(now)
    def tick(self,now,hp,predicted=None,mana=None,mana_predicted=None):
        ready=now>=self.next_input
        actions,events=self.hp.tick(now,hp,predicted,allow_skills=False,allow_dispatch=ready)
        ma,me=self.mp.tick(now,mana,mana_predicted,allow_skills=False,allow_dispatch=ready and not actions)
        events+=['Mana: '+e.replace('Auto Cura','Auto Mana') for e in me]
        if ma:actions=[('mana',key) for _,key in ma]
        if not actions:
            sa,se=self.hp.tick(now,hp,predicted,allow_skills=True,allow_dispatch=ready)
            actions+=sa;events+=se
        if actions:self.next_input=now+.08
        return actions,events


class ManaMonitor:
    def __init__(self,settings):
        self.settings=settings;self.filtered=HPFilter();self.forecast=HPFilter()
    def clear(self):self.filtered.clear();self.forecast.clear()
    def read(self,capture,area):
        m=self.settings
        if not m['enabled']:return dict(error='',used=None,predicted=None)
        if not m['roi'] or not m['color']:
            self.clear();return dict(error='Calibra la barra mana.',used=None,predicted=None)
        if [area['width'],area['height']]!=list(m['window_size']):
            self.clear();return dict(error='Dimensioni cambiate: ricalibra il mana.',used=None,predicted=None)
        x,y,w,h=m['roi'];roi=dict(left=area['left']+x,top=area['top']+y,width=w,height=h)
        if not any(roi['left']>=a['left'] and roi['top']>=a['top'] and
                   roi['left']+w<=a['left']+a['width'] and roi['top']+h<=a['top']+a['height']
                   for a in capture.monitors[1:]):
            self.clear();return dict(error='ROI mana fuori dal monitor.',used=None,predicted=None)
        from PIL import Image
        shot=capture.grab(roi)
        reading,mask=analyze_hp(Image.frombytes('RGB',shot.size,shot.rgb),m['color'],hue_tolerance=42)
        hp=self.filtered.update(reading.raw)
        predicted=self.forecast.update(reading.predicted if reading.raw is not None and reading.recovery_verified else None)
        if hp is not None and predicted is not None:predicted=max(hp,predicted)
        return dict(raw=reading.raw,used=hp,predicted=predicted,confidence=reading.confidence,
                    recovery=None if hp is None or predicted is None else round(predicted-hp,1),
                    error=reading.error.replace('HP','MP').replace('Rosso','Blu').replace('cura','recupero'),image=(shot.size,shot.rgb),
                    mask=None if mask is None else (shot.size,mask.tobytes()))
