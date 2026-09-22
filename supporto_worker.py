"""Small HP/MP ROI worker; foreground-gated dry run or shared key sender."""
import queue
import time
from supporto_core import HPFilter, analyze_hp
from supporto_mana import SupportCoordinator, ManaMonitor
from supporto_abilita import SkillMonitor


def latest(channel, value):
    try: channel.put_nowait(value)
    except queue.Full:
        try: channel.get_nowait()
        except queue.Empty: pass
        try: channel.put_nowait(value)
        except queue.Full: pass


def run_support(hwnd, config, stop, snapshots, events):
    def event(text):
        latest(events,(time.time(),text))
    engine=SupportCoordinator(config);config=engine.config
    skill_monitor=SkillMonitor(config['skills'])
    mana_monitor=ManaMonitor(config['mana']);last_mana_error=None
    filtered=HPFilter();forecast=HPFilter()
    clock=0.;last=time.monotonic();was_active=False;last_status=None;last_error=None
    sender=None;frame=None;mask=None;image_time=0.;frames=0;epoch=last
    try:
        from cattura_metin import api_windows, area_interna
        import mss
        from PIL import Image
        u=api_windows()
        mode='DRY RUN' if config['dry_run'] else 'INPUT REALI'
        if not config['dry_run']:
            from supporto_input import WindowsKeyboard,KeySender
            sender=KeySender(WindowsKeyboard(hwnd),stop)
        event('Supporto avviato — '+mode)
        with mss.mss() as capture:
            while not stop.is_set():
                now=time.monotonic();dt=now-last;last=now
                mana_sample={};skill_readings={}
                hp=None;raw=None;confidence=0.;error='';area=None;predicted=None;predicted_raw=None;recovery=None
                if dt>.5:
                    filtered.clear();forecast.clear();mana_monitor.clear()
                    for text in engine.suspend(clock):event(text)
                if not u.IsWindow(hwnd):
                    event('Finestra Metin2 chiusa — Supporto arrestato.')
                    latest(snapshots,dict(status='FINESTRA CHIUSA',state=engine.state,ended=True))
                    return
                active=bool(u.GetForegroundWindow()==hwnd and not u.IsIconic(hwnd))
                status='ATTIVO — '+mode if active else 'PAUSA — Metin2 non in primo piano'
                if active:
                    area=area_interna(u,hwnd)
                    if config['roi'] and [area['width'],area['height']]!=list(config['window_size']):
                        active=False;status='PAUSA — dimensioni cambiate: ricalibra HP'
                if active and config['roi']:
                    x,y,w,h=config['roi']
                    roi=dict(left=area['left']+x,top=area['top']+y,width=w,height=h)
                    if not any(roi['left']>=m['left'] and roi['top']>=m['top'] and
                               roi['left']+w<=m['left']+m['width'] and roi['top']+h<=m['top']+m['height']
                               for m in capture.monitors[1:]):
                        active=False;status='PAUSA — ROI fuori dal monitor'
                    else:
                        shot=capture.grab(roi)
                        # Discard a frame if focus or window origin changed during grab.
                        if stop.is_set():return
                        if u.GetForegroundWindow()!=hwnd or area_interna(u,hwnd)!=area:
                            active=False;status='PAUSA — finestra in movimento o focus cambiato'
                        else:
                            image=Image.frombytes('RGB',shot.size,shot.rgb)
                            reading,visual=analyze_hp(image,config['color'])
                            raw=reading.raw;confidence=reading.confidence;error=reading.error
                            hp=filtered.update(raw)
                            predicted_raw=reading.predicted if raw is not None and reading.recovery_verified else None
                            predicted=forecast.update(predicted_raw)
                            if hp is not None and predicted is not None:
                                predicted=max(hp,predicted);recovery=round(predicted-hp,1)
                            frames+=1
                            if now-image_time>=.2:
                                frame=(shot.size,shot.rgb)
                                mask=(shot.size,visual.tobytes()) if visual is not None else None
                                image_time=now
                elif active:
                    filtered.clear();forecast.clear();error='ROI HP non calibrata; monitor HP non disponibile.'
                if active:
                    try:mana_sample=mana_monitor.read(capture,area)
                    except Exception as exc:
                        mana_monitor.clear();mana_sample=dict(error=str(exc),used=None,predicted=None)
                    skill_readings=skill_monitor.read(capture,area)
                    if stop.is_set():return
                    if u.GetForegroundWindow()!=hwnd or area_interna(u,hwnd)!=area:
                        active=False;status='PAUSA — finestra in movimento o focus cambiato'
                        hp=None;predicted=None;mana_sample={};skill_readings={}
                if active:
                    if was_active:clock+=min(dt,.25)  # no catch-up after long capture stalls
                    actions,messages=engine.tick(clock,hp,predicted,mana_sample.get('used'),mana_sample.get('predicted'),skill_readings)
                    for text in messages:event(text)
                    for kind,key in actions:
                        if config['dry_run']:
                            event(f'DRY RUN: {kind} — avrei premuto {key}.')
                        elif sender.press(key):
                            event(f'INPUT REALE: {kind} — tasto {key} inviato a Windows.')
                        else:
                            engine.cancel_target_input()
                            event(f'Input {key} annullato: pausa, STOP o tastiera occupata.')
                            for text in engine.suspend(clock):event(text)
                else:
                    filtered.clear();forecast.clear();mana_monitor.clear()
                    for text in engine.suspend(clock):event(text)
                if status!=last_status:
                    event(status);last_status=status
                if error!=last_error:
                    if error:event('HP: '+error)
                    elif last_error:event('Lettura HP nuovamente disponibile.')
                    last_error=error
                mana_error=mana_sample.get('error','')
                if mana_error!=last_mana_error:
                    if mana_error:event('Mana: '+mana_error)
                    elif last_mana_error:event('Lettura mana nuovamente disponibile.')
                    last_mana_error=mana_error
                was_active=active
                latest(snapshots,dict(status=status,raw=raw,filtered=hp,used=hp if active else None,
                    skill_readings=skill_readings,skill_states=engine.skill_status(),
                    mana=mana_sample,mana_state=engine.mana_state,
                    predicted=predicted,predicted_raw=predicted_raw,recovery=recovery,
                    confidence=confidence,state=engine.state,error=error,countdowns=engine.countdowns(clock),
                    image=frame,mask=mask,image_time=image_time,fps=(frames/max(.001,now-epoch) if frames>=3 else 0.),ended=False))
                stop.wait(max(0,1/config['sample_hz']-(time.monotonic()-now)))
    except Exception as exc:
        import traceback
        event('Errore Supporto: '+str(exc))
        latest(snapshots,dict(status='ERRORE — Supporto arrestato',error=str(exc),
                            traceback=traceback.format_exc(),state=engine.state,ended=True))
    finally:
        if sender:
            try:
                sender.close()
                if sender.error:raise RuntimeError(sender.error)
            except Exception as exc:
                event('Errore rilascio tastiera: '+str(exc))
                latest(snapshots,dict(status='ERRORE TASTIERA — Supporto fermo',error=str(exc),state=engine.state,ended=True))
        event('Supporto fermo.')
