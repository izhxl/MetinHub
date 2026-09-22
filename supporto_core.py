"""Supporto: visual HP estimate and deterministic dry-run scheduler, no input APIs."""
from collections import deque
from dataclasses import dataclass
import math
from statistics import median

KEYS = (tuple('1234567890') + tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ') +
        tuple('F'+str(i) for i in range(1, 25) if i not in (6, 8)) +
        tuple('NUM'+str(i) for i in range(10)) +
        ('SPACE', 'TAB', 'ENTER', 'BACKSPACE', 'INSERT', 'DELETE',
         'HOME', 'END', 'PAGEUP', 'PAGEDOWN', 'UP', 'DOWN', 'LEFT', 'RIGHT'))


MODIFIERS = ('CTRL', 'ALT', 'SHIFT')


def normalize_key(value):
    """Canonical modifiers plus exactly one supported base key."""
    aliases={'CONTROL':'CTRL','SPAZIO':'SPACE','INVIO':'ENTER','RETURN':'ENTER',
             'CANC':'DELETE','SU':'UP','GIU':'DOWN','SINISTRA':'LEFT','DESTRA':'RIGHT'}
    parts=[aliases.get(p.strip().upper(),p.strip().upper()) for p in str(value).split('+')]
    key=parts[-1];mods=parts[:-1]
    if key in ('F6','F8'):
        raise ValueError('F6 e F8 sono riservati, anche con modificatori.')
    if key not in KEYS or any(m not in MODIFIERS for m in mods) or len(set(mods))!=len(mods):
        raise ValueError('Scrivi un tasto oppure una combinazione: ALT+1, CTRL+2, SHIFT+F1, CTRL+ALT+Q.')
    # Do not schedule desktop navigation, closing, or secure attention shortcuts.
    if ('ALT' in mods and key in ('TAB','F4','SPACE','ESC')) or ('CTRL' in mods and key=='ESC') or ('CTRL' in mods and 'ALT' in mods and key=='DELETE'):
        raise ValueError('Questa combinazione è riservata ai comandi di Windows.')
    return '+'.join([m for m in MODIFIERS if m in mods]+[key])


def defaults():
    return dict(auto_heal=False, threshold=50.0, rearm=60.0, heal_key='1', uses=3,
                burst_interval=.2, cooldown=2.0, sample_hz=15, skill_gap=1.0, dry_run=True,
                roi=None, window_size=None, color=None,
                skills=[dict(name='', key='F'+str(i+1), interval=30.0*(i+1), enabled=False)
                        for i in range(5)])


def validate(data, *, resource_only=False):
    if not isinstance(data, dict):
        raise ValueError('Configurazione Supporto non valida.')
    c = defaults()
    c.update(data)
    ranges = dict(threshold=(1, 98), rearm=(2, 100), burst_interval=(.1, 5),
                  cooldown=(.2, 120), sample_hz=(10, 20), skill_gap=(.1, 10))
    for name, (lo, hi) in ranges.items():
        try:
            value = float(str(c[name]).replace(',', '.'))
        except (ValueError, TypeError):
            raise ValueError('Valore non valido: '+name) from None
        if not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f'{name}: valore ammesso da {lo} a {hi}.')
        c[name] = value
    if c['rearm'] <= c['threshold']:
        raise ValueError('Il riarmo deve essere maggiore della soglia cura.')
    if isinstance(c['uses'], bool) or str(c['uses']) not in ('1', '2', '3', '4'):
        raise ValueError('Usi cura: scegli da 1 a 4.')
    c['uses'] = int(c['uses'])
    c['heal_key'] = normalize_key(c['heal_key'])
    if not isinstance(c['auto_heal'], bool):
        raise ValueError('Auto Cura deve essere ON oppure OFF.')
    if not isinstance(c['skills'], list) or len(c['skills']) != 5:
        raise ValueError('Sono richiesti cinque slot abilità.')
    skills = []
    for i, skill in enumerate(c['skills']):
        try:
            interval = float(str(skill['interval']).replace(',', '.'))
            key = normalize_key(skill['key'])
            enabled = skill['enabled']
            name = str(skill.get('name', '')).strip()[:50]
        except (TypeError, KeyError, ValueError):
            raise ValueError(f'Abilità {i+1}: dati non validi.') from None
        if not math.isfinite(interval) or not 1 <= interval <= 86400 or not isinstance(enabled, bool):
            raise ValueError(f'Abilità {i+1}: tasto non valido o intervallo fuori da 1–86400 s.')
        from supporto_abilita import validate_skill_visual
        skills.append(dict(name=name, key=key, interval=interval, enabled=enabled, **validate_skill_visual(skill)))
    c['skills'] = skills
    for key, length in (('roi', 4), ('window_size', 2)):
        v = c[key]
        if v is not None and (not isinstance(v, (list, tuple)) or len(v) != length or
                              any(type(n) is not int or n < 0 for n in v)):
            raise ValueError('Calibrazione non valida: '+key)
    if c['roi'] is not None:
        x,y,w,h = c['roi']
        if not 30 <= w <= 2048 or not 3 <= h <= 120 or w < h*4:
            raise ValueError('Seleziona solo l’interno della barra HP: larga e sottile, senza bordi.')
        if not c['window_size'] or x+w > c['window_size'][0] or y+h > c['window_size'][1]:
            raise ValueError('ROI fuori dalla finestra calibrata.')
    color = c['color']
    if color is not None:
        if not isinstance(color, dict) or not {'hue', 'value', 'saturation'} <= set(color) or set(color)-{'hue', 'value', 'saturation', 'rows', 'span', 'bright_rows', 'bright_values'}:
            raise ValueError('Profilo colore non valido: ricalibra la barra.')
        for key, maximum in (('hue', 360), ('value', 1), ('saturation', 1)):
            v = color[key]
            if not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= maximum:
                raise ValueError('Profilo colore fuori intervallo.')
        if 'rows' in color:
            rows=color['rows']
            if not isinstance(rows,list) or len(rows)<3 or any(type(r) is not int or r<0 or not c['roi'] or r>=c['roi'][3] for r in rows):
                raise ValueError('Linee campionate non valide: ricalibra HP.')
        if 'span' in color:
            span=color['span']
            if not isinstance(span,list) or len(span)!=2 or any(type(v) is not int for v in span) or not c['roi'] or not 0<=span[0]<span[1]<=c['roi'][2] or span[1]-span[0]<30:
                raise ValueError('Limiti interni HP non validi: ricalibra.')
        if 'bright_rows' in color or 'bright_values' in color:
            rr=color.get('bright_rows');vv=color.get('bright_values')
            if not isinstance(rr,list) or not isinstance(vv,list) or len(rr)!=3 or len(vv)!=3 or not c['roi'] or any(type(r) is not int or not 0<=r<c['roi'][3] for r in rr) or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=1 for v in vv):
                raise ValueError('Profilo luminosita HP non valido: ricalibra.')
    if not isinstance(c['dry_run'],bool):
        raise ValueError('Modalità test deve essere ON oppure OFF.')
    if not resource_only:
        from supporto_mana import validate_mana
        c['mana']=validate_mana(c.get('mana'))
    return c


@dataclass
class HPReading:
    raw: float | None
    confidence: float
    error: str = ''
    predicted: float | None = None
    recovery: float | None = None
    # True means the calibrated classifier returned a consistent estimate, not ground truth.
    recovery_verified: bool = False


def hsv(rgb):
    import numpy as np
    a = np.asarray(rgb, dtype=np.float32) / 255.0
    if a.ndim != 3 or a.shape[2] != 3:
        raise ValueError('La ROI deve essere RGB.')
    hi = a.max(axis=2); lo = a.min(axis=2); delta = hi-lo
    sat = delta / np.maximum(hi, 1e-6)
    hue = np.zeros_like(hi)
    r,g,b = (a[:,:,i] for i in range(3))
    active = delta > 1e-6
    for mask, value in ((active & (hi==r), ((g-b)/np.maximum(delta,1e-6))%6),
                        (active & (hi==g) & (hi!=r), (b-r)/np.maximum(delta,1e-6)+2),
                        (active & (hi==b) & (hi!=r) & (hi!=g), (r-g)/np.maximum(delta,1e-6)+4)):
        hue[mask] = value[mask]*60
    return hue,sat,hi


def calibrate(rgb, kind='hp'):
    """Learn from a manually selected, FULL bar with no potion effect."""
    import numpy as np
    hue,sat,val = hsv(rgb)
    hue_band=((hue<28)|(hue>332)) if kind=='hp' else ((hue>180)&(hue<270))
    red = hue_band & (sat>.35) & (val>.18)
    h,w = red.shape
    # Learn several filled scanlines; bevels and pale highlights are not HP.
    rows=np.flatnonzero(red.mean(axis=1)>=.80)
    if w < 30 or h < 3 or len(rows)<3:
        raise ValueError('Calibra con HP pieni e senza cura attiva; seleziona solo il riempimento rosso, senza cornice.')
    samples=red.copy();samples[[i for i in range(h) if i not in rows]]=False
    columns=np.flatnonzero(red[rows].mean(axis=0)>=.6)
    left,right=int(columns[0]),int(columns[-1])+1
    if right-left<30 or np.mean(red[rows,left:right])<.8:
        raise ValueError('Riempimento HP discontinuo: calibra con barra piena.')
    angles = hue[samples]; signed = (angles+180)%360-180
    levels=np.median(val[rows,left:right],axis=1)
    picks=np.argsort(levels)[-3:]
    bright_rows=[int(rows[i]) for i in picks]
    bright_values=[float(levels[i]) for i in picks]
    return dict(hue=float(np.median(signed)%360), value=float(np.median(val[samples])),
                saturation=float(np.median(sat[samples])), rows=[int(r) for r in rows], span=[left,right], bright_rows=bright_rows, bright_values=bright_values)


def analyze_hp(rgb, profile, *, hue_tolerance=26):
    """Fixed calibrated inner span + scanlines; visible red, not verified real HP."""
    import numpy as np
    hue,sat,val = hsv(rgb)
    h,w = hue.shape
    if not profile or h<3 or w<30:
        return HPReading(None,0,'ROI o calibrazione assente.'), None
    distance = np.abs((hue-profile['hue']+180)%360-180)
    mask = (distance<hue_tolerance) & (sat>max(.30,profile['saturation']*.45)) & (val>max(.13,profile['value']*.45))
    indices=profile.get('rows')
    if indices is None:indices=np.linspace(h*.25,h*.75-1,7).astype(int).clip(0,h-1)
    if any(i<0 or i>=h for i in indices):
        return HPReading(None,0,'Dimensioni ROI diverse dalla calibrazione.'),None
    left,right=profile.get('span',[0,w])
    if not 0<=left<right<=w or right-left<30:
        return HPReading(None,0,'Limiti della barra non validi: ricalibra HP.'),None
    rows = mask[indices,left:right]
    w=right-left
    endpoints=[]
    hole=max(3,round(w*.012))
    for row in rows:
        if not row[:max(2,round(w*.025))].any():
            continue
        gaps=np.convolve((~row).astype(int),np.ones(hole,dtype=int),'valid')
        where=np.flatnonzero(gaps==hole)
        end=int(where[0]) if len(where) else w
        if end<1:
            continue
        # Disjoint red patches beyond the edge suggest a bad ROI or animation.
        if row[min(w,end+hole):].sum()>max(3,w*.05):
            continue
        endpoints.append(end)
    # Debug shows only the calibrated sampling area, including its fixed origin.
    visible=np.zeros_like(mask)
    visible[np.asarray(indices)[:,None],np.arange(left,right)]=rows
    visual=(visible.astype('uint8')*255)
    if len(endpoints)<max(3,math.ceil(len(rows)*.65)):
        return HPReading(None,len(endpoints)/len(rows),'Rosso assente o discontinuo: 0 HP non confermabili, lettura esclusa.'),visual
    spread=float(np.percentile(endpoints,90)-np.percentile(endpoints,10))
    confidence=(len(endpoints)/len(rows))*max(0,1-spread/max(1,w*.12))
    if confidence<.65:
        return HPReading(None,confidence,'Linee di lettura discordanti: ROI/animazione da controllare.'),visual
    predicted=round(100*float(np.median(endpoints))/w,1)
    if 'bright_rows' not in profile:
        return HPReading(predicted,confidence),visual
    # The full HP texture has bright horizontal ridges; queued healing is darker.
    # Thresholds are relative to the user's full-bar calibration, not fixed RGB.
    rr=profile['bright_rows'];levels=profile['bright_values']
    if len(rr)!=3 or len(levels)!=3 or any(i<0 or i>=h for i in rr):
        return HPReading(None,0,'Profilo luminosità incompatibile: ricalibra.'),visual
    bright=mask[rr,left:right] & (val[rr,left:right]>=np.asarray(levels)[:,None]*.78)
    actual_ends=[]
    for row in bright:
        if not row[:max(2,round(w*.025))].any():continue
        gaps=np.convolve((~row).astype(int),np.ones(hole,dtype=int),'valid')
        where=np.flatnonzero(gaps==hole)
        end=int(where[0]) if len(where) else w
        if end<1 or row[min(w,end+hole):].sum()>max(3,w*.05):continue
        actual_ends.append(end)
    if len(actual_ends)<2 or max(actual_ends)-min(actual_ends)>max(3,w*.06):
        return HPReading(None,0,'HP/cura ambigui: luminosità discordante, lettura esclusa.'),visual
    actual=round(100*float(np.median(actual_ends))/w,1)
    if actual>predicted+3:
        return HPReading(None,0,'HP/cura discordanti: lettura esclusa.'),visual
    actual=min(actual,predicted)
    if predicted-actual<2:actual=predicted
    confidence=min(confidence,len(actual_ends)/3)
    # White: estimated current HP. Grey: queued healing. Black: excluded/empty.
    visual[visual>0]=100
    cutoff=left+round(actual*w/100)
    visual[:,left:cutoff]=np.where(visible[:,left:cutoff],255,0)
    return HPReading(actual,confidence,predicted=predicted,
                     recovery=round(predicted-actual,1),recovery_verified=True),visual


class HPFilter:
    def __init__(self):
        self.samples=deque(maxlen=3)
    def clear(self):
        self.samples.clear()
    def update(self, value):
        if value is None or not math.isfinite(value) or not 0<=value<=100:
            self.clear();return None
        self.samples.append(value)
        return float(median(self.samples)) if len(self.samples)==3 else None


class SupportEngine:
    """Timestamps are active foreground time; outputs are simulated intents only."""
    def __init__(self, config):
        self.config=validate(config,resource_only=True)
        self.state='READY';self.remaining=0;self.next_heal=0;self.blocked_at=0
        # Enabled slots are due on the first foreground tick of a new session.
        # Each subsequent deadline is set independently after its first dispatch.
        self.next_skill=[0.0 for s in self.config['skills']]
        from supporto_abilita import TargetState
        self.targets=[TargetState() for _ in self.config['skills']]
        self.visual_events=[];self.last_target=None
        self.next_dispatch=0;self.next_skill_dispatch=0;self.waiting_recovery=False
    def suspend(self, now):
        if self.state=='HEALING':
            self.state='BLOCKED';self.remaining=0;self.blocked_at=now
            return ['Burst annullato: pausa o lettura HP non valida. Auto Cura BLOCKED.']
        return []
    def tick(self, now, hp, predicted=None, *, allow_skills=True, allow_dispatch=True):
        events=[];actions=[];c=self.config
        if hp is None:
            events.extend(self.suspend(now))
        if c['auto_heal'] and hp is not None:
            if self.state=='BLOCKED' and now-self.blocked_at>=c['cooldown'] and hp>c['rearm']:
                self.state='READY';events.append('HP sopra soglia riarmo e cooldown trascorso — READY.')
            sufficient=predicted is not None and math.isfinite(predicted) and hp+2<=predicted<=100 and predicted>=c['threshold']
            waiting=self.state=='READY' and hp<c['threshold'] and sufficient
            if waiting and not self.waiting_recovery:
                events.append('Cura accodata sufficiente: attendo il recupero, nessun nuovo burst.')
            self.waiting_recovery=waiting
            if self.state=='READY' and hp<c['threshold'] and not sufficient:
                self.state='HEALING';self.remaining=c['uses'];self.next_heal=now
                events.append(f'HP {hp:.1f}% — Auto Cura attivata: {c["heal_key"]} x{c["uses"]} ({"DRY RUN" if c["dry_run"] else "INPUT REALI"}).')
        # At most one simulated key per tick: heal has priority; no catch-up spam.
        if allow_dispatch and now>=self.next_dispatch:
            if self.state=='HEALING' and hp is not None and now>=self.next_heal:
                actions.append(('cura',c['heal_key']))
                self.remaining-=1;self.next_heal=now+c['burst_interval']
                if self.remaining==0:
                    self.state='BLOCKED';self.blocked_at=now
                    events.append('Sequenza cura completata — BLOCKED.')
            elif allow_skills:
                # Oldest due slot first prevents short timers starving other skills.
                for i in sorted(range(len(c['skills'])),key=lambda i:(self.next_skill[i],i)):
                    s=c['skills'][i]
                    eligible=(self.targets[i].due(now,s['retry']) if s['mode']=='target' else now>=self.next_skill[i])
                    if s['enabled'] and eligible and now>=self.next_skill_dispatch:
                        actions.append((s['name'] or f'Abilità {i+1}',s['key']))
                        if s['mode']=='target':
                            self.targets[i].attempt(now);self.last_target=i
                            self.next_skill[i]=now+s['retry']
                        else:self.next_skill[i]=now+s['interval']
                        self.next_skill_dispatch=now+c['skill_gap']
                        break
            if actions:self.next_dispatch=now+.08
        return actions,events
    def observe_skills(self,now,readings):
        self.last_target=None
        messages=[]
        for i,s in enumerate(self.config['skills']):
            if s['enabled'] and s['mode']=='target':
                if self.targets[i].observe(now,readings.get(i,{}),s['interval']):
                    self.next_skill[i]=self.targets[i].deadline
                    messages.append(f"{s['name'] or 'Abilità '+str(i+1)}: attivazione confermata visivamente; timer {s['interval']:g} s avviato.")
        return messages
    def pause_targets(self):
        for t in self.targets:t.pause()
    def cancel_target_input(self):
        if self.last_target is not None:self.targets[self.last_target].pause()
        self.last_target=None
    def skill_status(self):
        return [t.label if s['mode']=='target' and s['enabled'] else '' for t,s in zip(self.targets,self.config['skills'])]
    def countdowns(self, now):
        return [max(0,(self.targets[i].deadline if s['mode']=='target' else max(d,self.next_skill_dispatch))-now) if s['enabled'] else None for i,(d,s) in enumerate(zip(self.next_skill,self.config['skills']))]


def detect_potion_icon(*_):
    """Reserved extension: no templates or automatic selection in phase 1."""
    return None
