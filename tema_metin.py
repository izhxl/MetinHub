"""Interfaccia MetinHub: navigazione, pannelli e intestazione vettoriale."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, font as tkfont

# Design tokens: tutti i componenti condivisi dipendono da questi valori.
COLORI = {
    'background': '#11171b', 'main_surface': '#141b20',
    'sidebar': '#0d1317', 'card': '#1b2227', 'card_secondary': '#181f24',
    'nav_hover': '#141b1f', 'nav_separator': '#20292e',
    'input': '#10171c', 'border': '#252e34', 'shadow': '#0c1115',
    'card_highlight': '#2c363d', 'preview_edge': '#202b32',
    'accent': '#bda172', 'accent_hover': '#c3a97c', 'accent_pressed': '#a48a5d',
    'text': '#eeeae2', 'muted': '#9ca7ad', 'disabled': '#687278',
    'secondary': '#242d33', 'secondary_hover': '#2b343a', 'secondary_pressed': '#20282e',
    'selected': '#2b2923', 'selected_hover': '#302d26', 'selected_border': '#65563d',
    'danger': '#2c2024', 'danger_hover': '#34262b', 'danger_pressed': '#251c1f',
    'danger_border': '#51343c', 'danger_text': '#d5a4a7',
    'scroll': '#465056', 'scroll_hover': '#58646b',
}
SPAZI = {'xs': 4, 'sm': 8, 'md': 12, 'lg': 16, 'xl': 24, 'xxl': 32}
RAGGI = {'button': 7, 'input': 6, 'card': 8, 'tab': 6}
FONT = {
    'page_title': ('Georgia', -34, 'bold'), 'page_title_compact': ('Georgia', -30, 'bold'),
    'section_title': ('Segoe UI', 12, 'bold'),
    'subsection_title': ('Segoe UI', 10, 'bold'),
    'body': ('Segoe UI', 10), 'label': ('Segoe UI', 10, 'bold'),
    'secondary': ('Segoe UI', 10), 'technical': ('Segoe UI', 9),
    'caption': ('Segoe UI', 9), 'status': ('Segoe UI', 10, 'bold'),
    'brand': ('Segoe UI', 15, 'bold'), 'eyebrow': ('Segoe UI', 9, 'bold'),
    'hero_caption': ('Segoe UI', 10), 'hero_caption_compact': ('Segoe UI', 9),
}
# Ritmo del testo: separato dalla geometria delle card e dei controlli.
RITMO_TESTO={'title_after': 6, 'label_gap': 2, 'paragraph_gap': 3, 'metadata_gap': 2}

BG=COLORI['main_surface']; PANEL=COLORI['card']; GOLD=COLORI['accent']
TEXT=COLORI['text']; MUTED=COLORI['muted']; BORDER=COLORI['border']

def geometria_iniziale(sw,sh,scala=1.0):
    """Finestra centrata, sempre più piccola dello schermo disponibile."""
    w=min(round(1440*scala),max(640,round(sw*.84)),max(320,sw-40))
    h=min(round(w/1.5),round(sh*.86))
    return w,h,max(0,(sw-w)//2),max(0,(sh-h)//2-15)

def controlli_arrotondati(root,style):
    # Elementi grafici ttk: click, tastiera, focus e disabled restano nativi.
    from PIL import Image,ImageDraw,ImageTk
    root._skin_images=[]
    def tile(fill,edge,radius=None):
        if radius is None:radius=RAGGI['button']
        im=Image.new('RGBA',(192,192),(0,0,0,0))
        draw=ImageDraw.Draw(im)
        draw.rounded_rectangle((4,4,184,184),radius=radius*4,fill=fill,outline=edge,width=4)
        im=im.resize((48,48),Image.Resampling.LANCZOS)
        photo=ImageTk.PhotoImage(im);root._skin_images.append(photo)
        return photo
    for name,normal,hover,pressed,edge in [
        ('TButton',COLORI['secondary'],COLORI['secondary_hover'],COLORI['secondary_pressed'],BORDER),
        ('Secondary.TButton',COLORI['secondary'],COLORI['secondary_hover'],COLORI['secondary_pressed'],BORDER),
        ('Primary.TButton',GOLD,COLORI['accent_hover'],COLORI['accent_pressed'],GOLD),
        ('Stop.TButton',COLORI['danger'],COLORI['danger_hover'],COLORI['danger_pressed'],COLORI['danger_border']),
        ('Danger.TButton',COLORI['danger'],COLORI['danger_hover'],COLORI['danger_pressed'],COLORI['danger_border']),
        ('Ghost.TButton',PANEL,COLORI['secondary'],COLORI['selected'],PANEL),
        ('Nav.TButton',COLORI['sidebar'],COLORI['nav_hover'],COLORI['selected'],COLORI['sidebar']),
        ('Selected.Nav.TButton',COLORI['selected'],COLORI['selected_hover'],COLORI['selected'],COLORI['selected_border'])]:
        plain=tile(normal,edge);active=tile(hover,edge);down=tile(pressed,edge)
        disabled=tile(COLORI['card_secondary'],BORDER);focus=tile(normal,GOLD)
        active_focus=tile(hover,GOLD);down_focus=tile(pressed,GOLD)
        if name in ('Nav.TButton','Selected.Nav.TButton'):
            selected=name=='Selected.Nav.TButton'
            def row(fill,focused=False,disabled_row=False):
                # Superficie piatta estesa: la slice sinistra mantiene la barra a 3 px.
                im=Image.new('RGBA',(48,48),fill)
                draw=ImageDraw.Draw(im)
                if selected:
                    draw.rectangle((0,0,2,47),fill=COLORI['disabled'] if disabled_row else GOLD)
                if focused:
                    # Indicatore da tastiera separato dalla selezione, senza cornice.
                    draw.rectangle((6,7,8,10),fill=MUTED)
                photo=ImageTk.PhotoImage(im);root._skin_images.append(photo)
                return photo
            plain=row(normal);active=row(hover);down=row(pressed)
            disabled=row(COLORI['sidebar'],disabled_row=True)
            focus=row(normal,True);active_focus=row(hover,True);down_focus=row(pressed,True)
        element='Metin.'+name+'.surface'
        style.element_create(element,'image',plain,
            ('disabled',disabled),('pressed','focus',down_focus),('active','focus',active_focus),
            ('pressed',down),('active',active),('focus',focus),('selected',down),
            border=12 if 'Nav.' in name else 8,width=1,height=1,sticky='nsew')
        style.layout(name,[(element,{'sticky':'nsew','children':[
            ('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
        # Il fondo rettangolare del widget deve coincidere con il contenitore.
        # Solo l'immagine disegna la superficie colorata del pulsante.
        background=COLORI['sidebar'] if 'Nav.' in name else PANEL
        style.configure(name,background=background,foreground=TEXT,padding=(SPAZI['md'],6),font=FONT['body'])
        style.map(name,background=[('disabled',background),('pressed',background),('active',background)],foreground=[('disabled',COLORI['disabled'])])
        if name=='Primary.TButton':style.configure(name,foreground=COLORI['input'],font=FONT['label'])
        if name in ('Stop.TButton','Danger.TButton'):style.configure(name,foreground=COLORI['danger_text'])
    for name in ('Nav.TButton','Selected.Nav.TButton'):
        style.configure(name,anchor='w',padding=(28,11),font=FONT['body'],foreground=MUTED)
        style.map(name,foreground=[('disabled',COLORI['disabled']),('active',TEXT)])
    style.configure('Selected.Nav.TButton',foreground=GOLD)
    campi_e_selettori(root,style,tile)
    def pill(color):
        im=Image.new('RGBA',(10,32),(0,0,0,0))
        ImageDraw.Draw(im).rounded_rectangle((2,0,7,31),radius=3,fill=color)
        photo=ImageTk.PhotoImage(im);root._skin_images.append(photo);return photo
    trough=pill(BG);thumb=pill(COLORI['scroll']);hover=pill(COLORI['scroll_hover']);pressed=pill(GOLD)
    style.element_create('Metin.Scroll.trough','image',trough,border=(0,4,0,4),sticky='nswe')
    style.element_create('Metin.Scroll.thumb','image',thumb,('pressed',pressed),('active',hover),border=(0,4,0,4),sticky='nswe')
    style.layout('Vertical.TScrollbar',[
        ('Metin.Scroll.trough',{'sticky':'ns','children':[
            ('Metin.Scroll.thumb',{'sticky':'nswe','expand':1})]})])
    style.configure('Vertical.TScrollbar',width=10,arrowsize=10)

def campi_e_selettori(root,style,tile):
    """Sostituisce solo la grafica, conservando elementi e binding nativi."""
    from PIL import Image,ImageDraw,ImageTk
    def sostituisci(layout,suffix,replacement):
        result=[]
        for name,options in layout:
            options=dict(options)
            if 'children' in options:
                options['children']=sostituisci(options['children'],suffix,replacement)
            result.append((replacement if name.endswith(suffix) else name,options))
        return result
    for name in ('TEntry','TSpinbox','TCombobox'):
        element='Metin.'+name+'.field'
        normal=tile(COLORI['input'],BORDER,RAGGI['input'])
        focus=tile(COLORI['input'],GOLD,RAGGI['input'])
        hover=tile(COLORI['input'],COLORI['card_highlight'],RAGGI['input'])
        disabled=tile(PANEL,BORDER,RAGGI['input'])
        invalid=tile(COLORI['input'],COLORI['danger_border'],RAGGI['input'])
        style.element_create(element,'image',normal,('disabled',disabled),('invalid',invalid),
                             ('focus',focus),('active',hover),border=9,sticky='nsew')
        style.layout(name,sostituisci(style.layout(name),'.field',element))
        style.configure(name,background=PANEL,fieldbackground=COLORI['input'],foreground=TEXT,
                        bordercolor=BORDER,padding=(SPAZI['sm'],6),arrowcolor=MUTED,
                        selectbackground=COLORI['selected'],selectforeground=TEXT)
        style.map(name,background=[('readonly',PANEL),('active',PANEL)],
                  foreground=[('disabled',COLORI['disabled']),('readonly',TEXT)],
                  fieldbackground=[('disabled',PANEL),('readonly',COLORI['input'])],
                  arrowcolor=[('disabled',COLORI['disabled']),('active',GOLD)])
    # Suffissi preservati: i binding ttk riconoscono *uparrow / *downarrow.
    # Nessun binding mouse o tastiera sostituito.
    def arrow(up,color):
        im=Image.new('RGBA',(96,56),(0,0,0,0))
        points=[(34,34),(48,20),(62,34)] if up else [(34,20),(48,34),(62,20)]
        ImageDraw.Draw(im).line(points,fill=color,width=5,joint='curve')
        photo=ImageTk.PhotoImage(im.resize((24,14),Image.Resampling.LANCZOS))
        root._skin_images.append(photo)
        return photo
    for widget,directions in (('TSpinbox',('uparrow','downarrow')),('TCombobox',('downarrow',))):
        layout=style.layout(widget)
        for direction in directions:
            element='Metin.'+widget+'.'+direction
            style.element_create(element,'image',arrow(direction=='uparrow',MUTED),
                ('disabled',arrow(direction=='uparrow',COLORI['disabled'])),
                ('pressed',arrow(direction=='uparrow',GOLD)),
                ('active',arrow(direction=='uparrow',TEXT)),sticky='')
            layout=sostituisci(layout,'.'+direction,element)
        if widget=='TCombobox':
            # Clam normally places the arrow beside the field: put both inside it.
            style.layout(widget,[('Metin.TCombobox.field',{'sticky':'nsew','children':[
                ('Metin.TCombobox.downarrow',{'side':'right','sticky':'ns'}),
                ('Combobox.padding',{'sticky':'nsew','children':[
                    ('Combobox.textarea',{'sticky':'nsew'})]})]})])
        else:style.layout(widget,layout)
        style.configure(widget,arrowcolor=MUTED,arrowsize=14)
    # Il popup resta quello di ttk: palette coerente anche nell'elenco aperto.
    root.option_add('*TCombobox*Listbox.background',COLORI['input'])
    root.option_add('*TCombobox*Listbox.foreground',TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground',COLORI['selected'])
    root.option_add('*TCombobox*Listbox.selectForeground',TEXT)
    root.option_add('*TCombobox*Listbox.font',FONT['body'])
    root.option_add('*TCombobox*Listbox.relief','flat')
    root.option_add('*TCombobox*Listbox.borderWidth',0)
    def toggle(selected=False,disabled=False,focus=False,active=False):
        image=Image.new('RGBA',(144,88),(0,0,0,0));draw=ImageDraw.Draw(image)
        fill=COLORI['disabled'] if disabled else (COLORI['accent_hover'] if active else GOLD) if selected else (COLORI['secondary'] if active else COLORI['secondary_hover'])
        draw.rounded_rectangle((4,8,136,80),radius=36,fill=fill,
                               outline=GOLD if focus else BORDER,width=4)
        x=72 if selected else 16
        draw.ellipse((x,20,x+48,68),fill=COLORI['muted'] if disabled else TEXT)
        photo=ImageTk.PhotoImage(image.resize((max(36,round(tkfont.Font(root=root,font=FONT['body']).metrics('linespace')*1.8)),max(22,round(tkfont.Font(root=root,font=FONT['body']).metrics('linespace')*1.1))),Image.Resampling.LANCZOS))
        root._skin_images.append(photo);return photo
    element='Metin.Checkbutton.indicator'
    style.element_create(element,'image',toggle(),('disabled','selected',toggle(True,True)),
                         ('disabled',toggle(False,True)),
                         ('pressed','selected',toggle(True,False,True,True)),('pressed',toggle(False,False,True,True)),
                         ('active','focus','selected',toggle(True,False,True,True)),('active','focus',toggle(False,False,True,True)),
                         ('active','selected',toggle(True,False,False,True)),('active',toggle(False,False,False,True)),
                         ('focus','selected',toggle(True,False,True)),('selected',toggle(True)),('focus',toggle(False,False,True)),sticky='w')
    # Il checkbutton diventa visivamente uno switch; la variabile resta identica.
    style.layout('TCheckbutton',sostituisci(style.layout('TCheckbutton'),'.indicator',element))
    style.configure('TCheckbutton',background=PANEL,foreground=TEXT,font=FONT['body'],padding=SPAZI['xs'])
    style.map('TCheckbutton',background=[('active',PANEL)],
              foreground=[('disabled',COLORI['disabled']),('active',TEXT)])
    style.configure('TNotebook',background=BG,borderwidth=0)
    style.configure('TNotebook.Tab',background=PANEL,foreground=MUTED,
                    padding=(SPAZI['lg'],SPAZI['sm']),font=FONT['label'])
    tab='Metin.Notebook.tab'
    style.element_create(tab,'image',tile(PANEL,BORDER,RAGGI['tab']),
                         ('disabled',tile(PANEL,BORDER,RAGGI['tab'])),
                         ('focus','selected',tile(COLORI['selected'],GOLD,RAGGI['tab'])),
                         ('focus',tile(PANEL,GOLD,RAGGI['tab'])),
                         ('selected',tile(COLORI['selected'],COLORI['selected_border'],RAGGI['tab'])),
                         ('active',tile(COLORI['secondary_hover'],BORDER,RAGGI['tab'])),border=9,sticky='nsew')
    style.layout('TNotebook.Tab',sostituisci(style.layout('TNotebook.Tab'),'.tab',tab))
    style.map('TNotebook.Tab',foreground=[('disabled',COLORI['disabled']),('selected',GOLD),('active',TEXT)],
              background=[('selected',BG),('active',BG)])

def applica_tema(root):
    barra_windows_scura(root)
    root.configure(background=COLORI['background'])
    sw,sh=root.winfo_screenwidth(),root.winfo_screenheight()
    scala=max(1.0,tkfont.Font(root=root,font=FONT['body']).measure('0')/8)
    w,h,x,y=geometria_iniziale(sw,sh,scala)
    root.geometry(f'{w}x{h}+{x}+{y}')
    root.minsize(min(860,w),min(540,h))
    root.option_add('*Font', FONT['body'])
    root.option_add('*Text.background', COLORI['input']); root.option_add('*Text.foreground',TEXT)
    root.option_add('*Text.insertBackground',GOLD)
    root.option_add('*Listbox.background',PANEL); root.option_add('*Listbox.foreground',TEXT)
    style=ttk.Style(root); style.theme_use('clam')
    style.configure('.',background=PANEL,foreground=TEXT,bordercolor=BORDER,
                    lightcolor=PANEL,darkcolor=PANEL,font=FONT['body'])
    style.configure('TSeparator',background=BORDER,bordercolor=BORDER,
                    lightcolor=BORDER,darkcolor=BORDER)
    style.configure('TFrame',background=BG)
    style.configure('Card.TFrame',background=PANEL)
    style.configure('TLabel',background=PANEL,foreground=TEXT)
    style.configure('Muted.TLabel',foreground=MUTED,font=FONT['secondary'])
    for role in ('page_title','section_title','subsection_title','body','label','secondary','technical','caption','status'):
        style.configure(role+'.TLabel',font=FONT[role],foreground=('#85939c' if role in ('technical','caption') else MUTED) if role in ('secondary','technical','caption') else TEXT,background=PANEL)
    style.configure('TButton',background=PANEL,foreground=TEXT,padding=(SPAZI['md'],SPAZI['sm']),borderwidth=0,focuscolor=GOLD,focusthickness=1)
    for name in ('TEntry','TSpinbox','TCombobox'):
        style.configure(name,fieldbackground=COLORI['input'],foreground=TEXT,padding=7,arrowsize=14)
    style.map('TCombobox',fieldbackground=[('readonly',COLORI['input'])],foreground=[('readonly',TEXT)])
    style.configure('TLabelframe',background=PANEL,bordercolor=BORDER,borderwidth=1)
    style.configure('TLabelframe.Label',foreground=TEXT,background=PANEL,font=FONT['section_title'])
    style.configure('TCheckbutton',background=PANEL,foreground=TEXT,padding=5)
    style.map('TCheckbutton',background=[('active',COLORI['secondary'])])
    style.configure('Vertical.TScrollbar',troughcolor=BG,background=BORDER,arrowcolor=MUTED,arrowsize=12)
    style.configure('TProgressbar',background=GOLD,troughcolor=PANEL)
    controlli_arrotondati(root,style)

# Ruoli visivi delle card esistenti; non influiscono sui comandi contenuti.
CARD_SECONDARIE=frozenset({'Comandi rapidi','Prove e diagnostica','Diagnostica'})

def superficie_secondaria(content):
    """Allinea solo i fondi al contenitore, ereditando font e controlli originali."""
    style=ttk.Style(content)
    def apply(widget):
        if isinstance(widget,ttk.Widget):
            current=widget.cget('style') or widget.winfo_class()
            name='SurfaceSecondary.'+current
            style.configure(name,background=COLORI['card_secondary'])
            style.map(name,background=[('disabled',COLORI['card_secondary']),
                                      ('pressed',COLORI['card_secondary']),
                                      ('active',COLORI['card_secondary'])])
            widget.configure(style=name)
        for child in widget.winfo_children():apply(child)
    if content.winfo_exists():apply(content)

def pannello(parent,titolo,descrizione=None,sfondo=PANEL,margine=BG):
    # Compatibilita cromatica con i contenitori delle pagine esistenti.
    margine=PANEL if margine=='#192024' else margine
    secondaria=titolo in CARD_SECONDARIE and sfondo==PANEL
    if secondaria:sfondo=COLORI['card_secondary']
    outer=tk.Canvas(parent,bg=margine,highlightthickness=0,height=100)
    outer.pack(fill='x',pady=(0,SPAZI['md']))
    frame_style='Card.TFrame' if sfondo==PANEL else 'SecondarySurface.TFrame' if secondaria else 'Preview.Card.TFrame'
    if sfondo!=PANEL:ttk.Style(parent).configure(frame_style,background=sfondo)
    content=ttk.Frame(outer,style=frame_style,padding=(10,8 if secondaria else 10))
    inset=4
    item=outer.create_window(inset,inset,window=content,anchor='nw')
    last=[None];pending=[None]
    def layout():
        pending[0]=None
        if not outer.winfo_exists():return
        w=max(100,outer.winfo_width());h=content.winfo_reqheight()+2*inset
        size=(w,h)
        if size==last[0]:return
        previous=last[0];last[0]=size
        if previous is None or previous[0]!=w:outer.itemconfigure(item,width=max(80,w-2*inset))
        if previous is None or previous[1]!=h:outer.configure(height=h)
        outer.delete('bordo');r=RAGGI['card']*2
        outer.create_polygon(r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1,
                             smooth=True,splinesteps=16,fill=sfondo,outline=BORDER,tags='bordo')
        # Luce radente di un pixel, solo sulle card rialzate.
        if sfondo==PANEL:
            outer.create_line(r,2,w-r,2,fill=COLORI['card_highlight'],tags='bordo')
        outer.create_line(r,h-2,w-r,h-2,fill=COLORI['shadow'],tags='bordo')
        outer.tag_lower('bordo')
    def schedule(e=None):
        if pending[0] is None:pending[0]=outer.after_idle(layout)
    outer.bind('<Configure>',schedule);content.bind('<Configure>',schedule)
    if titolo:ttk.Label(content,text=titolo,style=('subsection_title' if secondaria else 'section_title')+'.TLabel').pack(anchor='w',pady=(0,RITMO_TESTO['title_after']))
    if descrizione:testo(content,descrizione,muted=True)
    if secondaria:content.after_idle(lambda:superficie_secondaria(content))
    return content

class Colonne(ttk.Frame):
    """Due colonne sulle finestre ampie, una sulle finestre strette."""
    def __init__(self,parent):
        super().__init__(parent);self.pack(fill='x')
        self.sinistra=ttk.Frame(self);self.destra=ttk.Frame(self)
        self._wide=None
        self._threshold=max(780,tkfont.Font(font=FONT['body']).measure('0')*100)
        self.bind('<Configure>',self._layout)
    def _layout(self,event):
        # La soglia segue la dimensione reale del font sul monitor.
        # Isteresi: niente alternanza continua vicino al cambio di colonne.
        margin=-20 if self._wide else 20
        wide=event.width>=self._threshold+margin
        if wide==self._wide:return
        self._wide=wide
        self.sinistra.grid_forget();self.destra.grid_forget()
        self.columnconfigure(0,weight=3,uniform='colonne')
        self.columnconfigure(1,weight=2 if wide else 0,uniform='colonne' if wide else '')
        self.sinistra.grid(row=0,column=0,sticky='new',padx=(0,SPAZI['md'] if wide else 0))
        self.destra.grid(row=0 if wide else 1,column=1 if wide else 0,sticky='new')

def testo(parent,text=None,textvariable=None,muted=False,role=None,**kw):
    role=role or ('secondary' if muted else 'body')
    label=ttk.Label(parent,text=text,textvariable=textvariable,justify='left',
                    style=role+'.TLabel',**kw)
    gap=RITMO_TESTO['label_gap'] if role=='label' else RITMO_TESTO['metadata_gap'] if role in ('caption','technical') else RITMO_TESTO['paragraph_gap']
    label.pack(anchor='w',fill='x',pady=gap)
    last=[None];pending=[None];width=[150]
    def apply_wrap():
        pending[0]=None
        if label.winfo_exists() and width[0]!=last[0]:
            last[0]=width[0];label.configure(wraplength=width[0])
    def resize(e):
        width[0]=max(80,e.width-28)
        if width[0]!=last[0] and pending[0] is None:pending[0]=label.after_idle(apply_wrap)
    parent.bind('<Configure>',resize,add='+')
    return label

def icona_sidebar(nome,colore,size=22):
    """Quattro pittogrammi a tratto uniforme, su fondo trasparente."""
    from PIL import Image, ImageDraw
    image=Image.new('RGBA',(96,96),(0,0,0,0));draw=ImageDraw.Draw(image)
    def line(points):
        draw.line([(x*4,y*4) for x,y in points],fill=colore,width=6,joint='curve')
    if nome=='Schegge':
        line([(9,3),(17,5),(21,13),(13,22),(4,15),(9,3)])
        line([(9,3),(10,13),(13,22)])
        line([(17,5),(10,13),(4,15)])
        line([(10,13),(21,13)])
    elif nome=='Pesca':
        draw.ellipse((12,24,72,72),outline=colore,width=6)
        line([(18,10),(22,6),(22,18),(18,14)])
        draw.ellipse((28,40,34,46),fill=colore)
        line([(10,6),(13,3),(15,7)])
    elif nome=='Supporto':
        line([(9,3),(15,3),(15,9),(21,9),(21,15),(15,15),(15,21),(9,21),(9,15),(3,15),(3,9),(9,9),(9,3)])
    elif nome=='Impostazioni':
        for y in (6,12,18):line([(3,y),(21,y)])
        for x,y in ((8,6),(16,12),(10,18)):
            draw.rounded_rectangle((x*4-6,y*4-10,x*4+6,y*4+10),radius=3,
                                   fill=COLORI['sidebar'],outline=colore,width=5)
    elif nome=='Installazione':
        line([(12,3),(12,15)])
        line([(7,10),(12,15),(17,10)])
        line([(4,15),(4,21),(20,21),(20,15)])
    return image.resize((size,size),Image.Resampling.LANCZOS)

def trattamento_hero_schegge(frame):
    """Trattamento del solo banner Schegge; calcolato dopo il debounce."""
    from PIL import Image, ImageDraw
    w,h=frame.size
    # Gradiente orizzontale: testo protetto, panorama ancora riconoscibile.
    ramp=Image.new('RGBA',(256,1))
    ramp.putdata([(8,14,18,round(185-145*(x/255)**0.8)) for x in range(256)])
    result=Image.alpha_composite(frame.convert('RGBA'),ramp.resize((w,h),Image.Resampling.BILINEAR))
    fade=Image.new('RGBA',(1,128))
    fade_rgb=tuple(int(BG[i:i+2],16) for i in (1,3,5))
    fade.putdata([(*fade_rgb,round(65*max(0,(y/127-.62)/.38))) for y in range(128)])
    result=Image.alpha_composite(result,fade.resize((w,h),Image.Resampling.BILINEAR))
    # Maschera antialias con lo stesso radius delle card.
    mask=Image.new('L',(w*2,h*2),0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,w*2-1,h*2-1),radius=RAGGI['card']*2,fill=255)
    mask=mask.resize((w,h),Image.Resampling.LANCZOS)
    base=Image.new('RGBA',(w,h),BG);base.paste(result,(0,0),mask)
    ImageDraw.Draw(base).rounded_rectangle((0,0,w-1,h-1),radius=RAGGI['card'],outline=BORDER,width=1)
    return base

class Navigazione(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent);self.pages={};self.buttons={};self.current=None
        self.sidebar=tk.Frame(self,bg=COLORI['sidebar']);self.sidebar.pack(side='left',fill='y')
        tk.Frame(self.sidebar,bg=COLORI['nav_separator'],width=1).pack(side='right',fill='y')
        brand=tk.Frame(self.sidebar,bg=COLORI['sidebar'])
        brand.pack(fill='x',padx=24,pady=(30,36))
        from PIL import Image, ImageTk
        scale=max(1.0,tkfont.Font(root=self,font=FONT['body']).measure('0')/8)
        with Image.open(Path(__file__).with_name('MetinHub.png')) as logo:
            size=round(44*scale)
            self.logo=ImageTk.PhotoImage(logo.resize((size,size),Image.Resampling.LANCZOS))
        tk.Label(brand,image=self.logo,bg=COLORI['sidebar'],borderwidth=0).pack(side='left',padx=(0,12))
        titles=tk.Frame(brand,bg=COLORI['sidebar']);titles.pack(side='left')
        tk.Label(titles,text='MetinHub',fg=TEXT,bg=COLORI['sidebar'],font=FONT['brand']).pack(anchor='w')
        tk.Label(titles,text='Compagno di gioco',fg=MUTED,bg=COLORI['sidebar'],font=FONT['caption']).pack(anchor='w',pady=(3,0))
        tk.Label(self.sidebar,text='STRUMENTI',fg=COLORI['disabled'],bg=COLORI['sidebar'],
                 font=FONT['caption']).pack(anchor='w',padx=28,pady=(0,10))
        self.menu=tk.Frame(self.sidebar,bg=COLORI['sidebar']);self.menu.pack(fill='x')
        footer=tk.Frame(self.sidebar,bg=COLORI['sidebar'])
        footer.pack(side='bottom',fill='x',padx=24,pady=(14,20))
        tk.Frame(footer,height=1,bg=COLORI['nav_separator']).pack(fill='x',pady=(0,14))
        tk.Label(footer,text='F6  Avvia / pausa   ·   F8  Stop',fg=MUTED,bg=COLORI['sidebar'],
                 font=FONT['caption']).pack(anchor='w')
        title=self.winfo_toplevel().title()
        version=title[len('MetinHub '):] if title.startswith('MetinHub ') else ''
        tk.Label(footer,text=('Versione '+version) if version else 'MetinHub',
                 fg=COLORI['disabled'],bg=COLORI['sidebar'],font=FONT['caption']).pack(anchor='w',pady=(12,0))
        self.lower_menu=tk.Frame(self.sidebar,bg=COLORI['sidebar'])
        self.lower_menu.pack(side='bottom',fill='x')
        # Create una volta: nessuna rasterizzazione durante il ridimensionamento.
        self.nav_icons={}
        self.button_icons={}
        for name in ('Schegge','Pesca','Supporto','Impostazioni','Installazione'):
            self.nav_icons[name]=tuple(ImageTk.PhotoImage(icona_sidebar(name,color,round(22*scale)))
                                      for color in (MUTED,GOLD))
        self.body=ttk.Frame(self,padding=(SPAZI['lg'],SPAZI['md']));self.body.pack(side='left',fill='both',expand=True)
        with Image.open(Path(__file__).with_name('panorama_metin.png')) as panorama:
            self.panorama=panorama.convert('RGB')
        self.hero=tk.Canvas(self.body,height=190,bg=PANEL,highlightthickness=0)
        self._header_job=None;self._header_key=None
        self.hero.pack(fill='x',pady=(0,SPAZI['md']));self.hero.bind('<Configure>',self._schedule_header)
        self.body.bind('<Configure>',self._resize_body)
        self.host=ttk.Frame(self.body);self.host.pack(fill='both',expand=True)
        self.bind_all('<MouseWheel>',self._wheel,add='+')
        self._wheel_remainder=0

    def _resize_body(self,event):
        # Un solo percorso di dimensionamento: evita rimbalzi tra resize e render.
        self._schedule_header()

    def _schedule_header(self,event=None):
        # Throttle instead of debounce: continuous dragging cannot postpone rendering.
        if self._header_job is None:
            self._header_job=self.after(33,self._header)

    def _header(self):
        from PIL import Image, ImageTk, ImageOps
        self._header_job=None
        c=self.hero;w=max(200,c.winfo_width());h=max(112,c.winfo_height())
        title=self.buttons[self.current].cget('text').strip() if self.current else 'MetinHub'
        title=title.split('  ',1)[-1]
        schegge=title in ('Schegge','Pesca','Supporto','Impostazioni','Installazione')
        desired=max(120,min(160,round(self.body.winfo_height()*.19))) if schegge else max(112,min(190,round(self.body.winfo_height()*.22)))
        if schegge:
            pad=SPAZI['xl'];available=max(100,w-pad*2)
            description={'Schegge':'Riconosci. Segui. Raccogli.','Pesca':'Segui il minigioco, controlla ogni colpo.','Supporto':'HP e abilità, prima in simulazione.','Impostazioni':'Tempi, prestazioni e diagnostica.','Installazione':'Componenti e aggiornamenti del programma.'}.get(title,'')
            title_font=FONT['page_title_compact'] if desired<150 else FONT['page_title']
            heights=[]
            # Misura il vero wrapping di Tk, incluso il DPI corrente.
            for value,font in (('METINHUB  /  STRUMENTI',FONT['caption']),
                               (title,title_font),(description,FONT['hero_caption_compact'])):
                item=c.create_text(-10000,-10000,text=value,font=font,width=available,anchor='nw')
                box=c.bbox(item);heights.append(box[3]-box[1] if box else 0);c.delete(item)
            text_height=sum(heights)+16
            desired=max(desired,text_height+32)
            top=(desired-text_height)//2
            positions=(top,top+heights[0]+8,top+heights[0]+heights[1]+16)
        if int(c.cget('height'))!=desired:
            c.configure(height=desired)
            self._schedule_header()
            return
        key=(w,h,self.current)
        if key==self._header_key:return
        previous=self._header_key;self._header_key=key;c.delete('all')
        if previous is None or previous!=key:
            frame=ImageOps.fit(self.panorama,(w,h),Image.Resampling.BILINEAR,centering=(0.5,0.52))
            if schegge:frame=trattamento_hero_schegge(frame)
            self.hero_photo=ImageTk.PhotoImage(frame)
        c.create_image(0,0,image=self.hero_photo,anchor='nw')
        if schegge:
            for y,value,font,color in (
                (positions[0],'METINHUB  /  STRUMENTI',FONT['caption'],MUTED),
                (positions[1],title,title_font,TEXT),
                (positions[2],description,FONT['hero_caption_compact'],MUTED)):
                c.create_text(pad,y,text=value,fill=color,anchor='nw',font=font,width=available)
            return
        c.create_line(0,h-1,w,h-1,fill=COLORI['selected_border'])
        title=self.buttons[self.current].cget('text').strip() if self.current else 'MetinHub'
        title=title.split('  ',1)[-1]
        descriptions={'Schegge':'Riconosci. Segui. Raccogli.', 'Pesca':'Ogni colpo conta. Il contatore conferma.','Supporto':'HP e abilità, prima in simulazione.',
                      'Impostazioni':'Il ritmo giusto per il tuo computer.', 'Installazione':'Tutto pronto, su ogni PC.'}
        c.create_text(24,round(h*.12),text='METINHUB  /  STRUMENTI',fill=MUTED,anchor='nw',font=FONT['eyebrow'])
        c.create_text(24,round(h*.34),text=title,fill=TEXT,anchor='nw',font=FONT['page_title_compact'] if h<145 else FONT['page_title'])
        c.create_text(24,round(h*.73),text=descriptions.get(title,''),fill=TEXT,anchor='nw',font=FONT['hero_caption_compact'] if h<145 else FONT['hero_caption'],width=max(150,w-48))

    def nuova_pagina(self):
        wrapper=ttk.Frame(self.host);canvas=tk.Canvas(wrapper,bg=BG,highlightthickness=0)
        scroll=ttk.Scrollbar(wrapper,orient='vertical',command=canvas.yview)
        canvas.pack(side='left',fill='both',expand=True)
        page=ttk.Frame(canvas);item=canvas.create_window(0,0,anchor='nw',window=page)
        last_region=[None];last_width=[None]
        def sized(e=None):
            region=canvas.bbox('all')
            if region!=last_region[0]:
                last_region[0]=region;canvas.configure(scrollregion=region)
            needs=page.winfo_reqheight()>canvas.winfo_height()+2
            if needs and not scroll.winfo_manager():scroll.pack(side='right',fill='y')
            elif not needs and scroll.winfo_manager():scroll.pack_forget()
        page.bind('<Configure>',sized)
        def width(e):
            if e.width!=last_width[0]:
                last_width[0]=e.width;canvas.itemconfigure(item,width=e.width)
            sized()
        canvas.bind('<Configure>',width);canvas.configure(yscrollcommand=scroll.set)
        self.pages[str(page)]=(wrapper,canvas)
        return page

    def _wheel(self,event):
        # Nessun bind globale che intercetti altri dialoghi o i campi numerici.
        if self.current is None:return
        widget=event.widget
        if widget.winfo_toplevel()!=self.winfo_toplevel():return
        if widget.winfo_class() in ('TSpinbox','TCombobox','Text'):return
        wrapper,canvas=self.pages[self.current]
        if canvas.yview()!=(0.0,1.0):
            self._wheel_remainder+=event.delta/120
            steps=int(self._wheel_remainder)
            self._wheel_remainder-=steps
            if steps:canvas.yview_scroll(-steps,'units')

    def add(self,page,text):
        key=str(page)
        icons=self.nav_icons[text];self.button_icons[key]=icons
        parent=self.lower_menu if text=='Impostazioni' else self.menu
        button=ttk.Button(parent,text='  '+text,image=icons[0],compound='left',
            style='Nav.TButton',cursor='hand2',command=lambda:self.select(key))
        button.pack(fill='x',pady=3);self.buttons[key]=button
        if self.current is None:self.select(key)

    def select(self,page=None):
        if page is None:return self.current
        key=str(page)
        if self.current is not None:
            self.pages[self.current][0].pack_forget();self.buttons[self.current].configure(style='Nav.TButton',image=self.button_icons[self.current][0])
        self.current=key;self.pages[key][0].pack(fill='both',expand=True)
        self.buttons[key].configure(style='Selected.Nav.TButton',image=self.button_icons[key][1]);self._schedule_header()
        return key


def stato_visivo(messaggio):
    """Etichetta sintetica; il messaggio originale resta sempre visibile."""
    value=messaggio.casefold()
    if value.startswith('stop.'):
        return 'ARRESTATO', COLORI['danger_text']
    if value.startswith('in pausa'):
        return 'IN PAUSA', GOLD
    if value.startswith(('analisi ocr', 'raccolta live')):
        return 'ANALISI ATTIVA', GOLD
    if value.startswith(('avvio ocr', 'caricamento')):
        return 'AVVIO ANALISI', MUTED
    if value.startswith(('in attesa', 'ripresa:', 'riavvio richiesto')):
        return 'IN ATTESA', MUTED
    if value.startswith(('metin2 selezionato', 'area impostata')):
        return 'PRONTO', TEXT
    if value.startswith(('premi scegli', 'prima premi', 'porta metin2', 'disegna')):
        return 'PREPARAZIONE', MUTED
    return 'STATO SESSIONE', MUTED


class LayoutSchegge(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent)
        self.pack(fill='x')
        self.sinistra=ttk.Frame(self);self.destra=ttk.Frame(self)
        self._wide=None
        self._control_limit=round(480*max(1.0,tkfont.Font(font=FONT['body']).measure('0')/8))
        self.threshold=max(840,tkfont.Font(font=FONT['body']).measure('0')*108)
        self.bind('<Configure>',self._layout)

    def _layout(self,event):
        wide=event.width>=self.threshold+(-20 if self._wide else 20)
        self.columnconfigure(1,minsize=min(self._control_limit,round(event.width*.36)) if wide else 0)
        if wide==self._wide:return
        self._wide=wide
        self.sinistra.grid_forget();self.destra.grid_forget()
        # Anteprima protagonista; il pannello comandi conserva una larghezza leggibile.
        self.columnconfigure(0,weight=1,uniform='')
        self.columnconfigure(1,weight=0,uniform='')
        self.sinistra.grid(row=0,column=0,sticky='new',padx=(0,SPAZI['md'] if wide else 0))
        self.destra.grid(row=0 if wide else 1,column=1 if wide else 0,sticky='new')


def altezza_anteprima(width,window_height,ratio,fraction):
    return max(210,min(round(width*ratio),round(window_height*fraction)))


class AnteprimaTerreno(tk.Canvas):
    """Superficie di anteprima adattiva con la stessa API configure usata dalla pagina."""
    def __init__(self,parent):
        super().__init__(parent,background=COLORI['input'],highlightthickness=0,
                         width=1,height=260,borderwidth=0)
        self._source=None;self._photo=None
        self._text='Nessuna cattura disponibile\n\nSeleziona un’area e avvia la raccolta.'
        self._pending=None;self._last=None
        self._preview_toplevel=self.winfo_toplevel();self._root_height=None
        self._root_binding=self._preview_toplevel.bind('<Configure>',self._resize_window,add='+')
        self.bind('<Configure>',self._schedule)
        self.bind('<Destroy>',self._destroy,add='+')
        self._schedule()

    def configure(self,cnf=None,**kw):
        # Il chiamante mantiene esattamente image/text/padding già esistenti.
        if isinstance(cnf,dict):kw={**cnf,**kw};cnf=None
        visual=False
        from PIL import ImageTk
        if 'image' in kw:
            photo=kw.pop('image')
            self._source=ImageTk.getimage(photo) if photo else None
            visual=True
        if 'text' in kw:self._text=kw.pop('text');visual=True
        kw.pop('padding',None);kw.pop('wraplength',None)
        if visual:self._last=None;self._schedule()
        if cnf is not None or kw:return super().configure(cnf,**kw)
    config=configure

    def _resize_window(self,event):
        if event.widget is self._preview_toplevel and event.height!=self._root_height:
            self._root_height=event.height
            if self.winfo_ismapped():self._schedule()

    def _preview_height(self,width,ratio,fraction):
        # Screen-independent: adapt to the actual client height, not resolution.
        return altezza_anteprima(width,self._preview_toplevel.winfo_height(),ratio,fraction)

    def _destroy(self,event):
        if event.widget is self and self._root_binding:
            self._preview_toplevel.unbind('<Configure>',self._root_binding);self._root_binding=None
        if event.widget is self and self._pending is not None:
            self.after_cancel(self._pending);self._pending=None

    def _schedule(self,event=None):
        if self._pending is not None:self.after_cancel(self._pending)
        self._pending=self.after(60,self._draw)

    def _draw(self):
        from PIL import Image, ImageTk
        self._pending=None
        w=max(120,self.winfo_width());h=max(210,min(getattr(self,'altezza_massima',370),round(w*getattr(self,'rapporto',.56))))
        if int(self.cget('height'))!=h:super().configure(height=h)
        key=(w,h)
        if key==self._last:return
        self._last=key;self.delete('all')
        # Bordo incassato: separa il terreno dalla superficie della card.
        self.create_rectangle(0,0,w-1,h-1,outline=COLORI['preview_edge'])
        self.create_line(1,1,w-2,1,fill=COLORI['shadow'])
        if self._source is not None:
            frame=self._source.copy()
            frame.thumbnail((max(1,w-16),h-16),Image.Resampling.BILINEAR)
            self._photo=ImageTk.PhotoImage(frame)
            self.create_image(w/2,h/2,image=self._photo)
        else:
            # Un indicatore di inquadratura sobrio, senza ulteriori pannelli.
            x=w/2;y=h*.28
            for sx,sy in ((-1,-1),(1,-1),(-1,1),(1,1)):
                self.create_line(x+sx*12,y+sy*5,x+sx*12,y+sy*12,x+sx*5,y+sy*12,
                                 fill=COLORI['disabled'],width=2)
            self.create_text(w/2,h*.56,text=self._text,fill=MUTED,
                             font=FONT['body'],justify='center',width=max(100,w-48))



class AnteprimaSchegge(AnteprimaTerreno):
    """Solo resa della preview Schegge; Pesca conserva la propria presentazione."""
    def _draw(self):
        from PIL import Image,ImageTk
        self._pending=None
        w=max(120,self.winfo_width())
        h=self._preview_height(w,.56,.64)
        if int(self.cget('height'))!=h:tk.Canvas.configure(self,height=h)
        key=(w,h)
        if key==self._last:return
        self._last=key;self.delete('all')
        self.create_rectangle(0,0,w-1,h-1,outline=COLORI['preview_edge'])
        if self._source is not None:
            iw,ih=self._source.size
            scale=min((w-8)/iw,(h-8)/ih)
            size=(max(1,round(iw*scale)),max(1,round(ih*scale)))
            # Fit completo, senza ritagliare etichette o alterare le coordinate OCR.
            self._photo=ImageTk.PhotoImage(self._source.resize(size,Image.Resampling.BILINEAR))
            self.create_image(w/2,h/2,image=self._photo)
            return
        title,separator,description=self._text.partition('\n\n')
        # Per i messaggi successivi si conserva integralmente il testo originale.
        for sx,sy in ((-1,-1),(1,-1),(-1,1),(1,1)):
            self.create_line(sx*13,sy*5,sx*13,sy*13,sx*5,sy*13,
                             fill=MUTED,width=2,tags='empty')
        heading=self.create_text(0,31,text=title,fill=TEXT,font=FONT['subsection_title'],
                                 anchor='n',justify='center',width=max(100,w-48),tags='empty')
        bottom=self.bbox(heading)[3]
        if separator:
            self.create_text(0,bottom+8,text=description,fill=MUTED,font=FONT['secondary'],
                             anchor='n',justify='center',width=max(100,w-48),tags='empty')
        x1,y1,x2,y2=self.bbox('empty')
        self.move('empty',w/2-(x1+x2)/2,h/2-(y1+y2)/2)

def costruisci_schegge(parent,stato,tasti,click_testo,riepilogo,area_testo):
    layout=LayoutSchegge(parent)
    visuale=pannello(layout.sinistra,'Anteprima del terreno',
                     'L’ultima cattura della zona selezionata.')
    preview=AnteprimaSchegge(visuale)
    preview.pack(fill='x',pady=(4,8))
    ttk.Label(visuale,text='RISULTATO DELL’ANALISI',style='Muted.TLabel',
              font=FONT['subsection_title']).pack(anchor='w',pady=(0,SPAZI['xs']))
    testo(visuale,textvariable=riepilogo,role='technical')

    controllo=pannello(layout.destra,'Sessione di raccolta')
    badge=ttk.Label(controllo,font=FONT['status'],padding=(8,4),background=COLORI['input'])
    badge.pack(anchor='w',pady=(0,SPAZI['sm']))
    def aggiorna(*_):
        label,color=stato_visivo(stato.get())
        badge.configure(text='●  '+label,foreground=color)
    token=stato.trace_add('write',aggiorna)
    def cleanup(event):
        if event.widget is badge:stato.trace_remove('write',token)
    badge.bind('<Destroy>',cleanup,add='+');aggiorna()
    testo(controllo,textvariable=stato,muted=True)
    barra=ttk.Frame(controllo,style='Card.TFrame')
    barra.pack(fill='x',pady=(SPAZI['md'],SPAZI['sm']))
    barra.columnconfigure(0,weight=1)

    # Dati tecnici nella stessa card: separazione tipografica, niente card annidate.
    ttk.Separator(controllo,orient='horizontal').pack(fill='x',pady=(8,12))
    ttk.Label(controllo,text='AREA E PRESTAZIONI',style='Muted.TLabel',
              font=FONT['caption']).pack(anchor='w')
    testo(controllo,textvariable=area_testo,role='technical')
    dettagli=pannello(layout.destra,'Comandi rapidi')
    dettagli.configure(padding=(10,6))
    testo(dettagli,textvariable=tasti,role='caption')
    testo(dettagli,textvariable=click_testo,role='caption')
    return layout,controllo,barra,visuale,preview


class AzioniSessione(ttk.Frame):
    """Barra di azioni che passa da riga a colonna senza cambiare i comandi."""
    def __init__(self,parent):
        super().__init__(parent,style='Card.TFrame')
        self.pack(fill='x',pady=(12,4));self._wide=None
        self.bind('<Configure>',self._arrange)
    def _arrange(self,event):
        if not hasattr(self,'_buttons'):
            self._buttons=sorted(self.winfo_children(),key=lambda b:int(b.grid_info().get('row',0)))
        buttons=self._buttons
        wide=event.width>=max(660,tkfont.Font(font=FONT['body']).measure('0')*88)
        if wide==self._wide:return
        self._wide=wide
        for i in range(len(buttons)):self.columnconfigure(i,weight=0)
        for i,button in enumerate(buttons):
            button.grid_forget()
            self.columnconfigure(i if wide else 0,weight=0 if wide else 1)
            button.grid(row=0 if wide else i,column=i if wide else 0,sticky='ew',
                        padx=(0,8 if wide and i<len(buttons)-1 else 0),pady=4)


def stato_evidenza(parent,variabile):
    """Evidenzia il messaggio reale, senza dedurre o modificare lo stato operativo."""
    label=testo(parent,textvariable=variabile,role='status',padding=(8,4),background=COLORI['input'])
    def aggiorna(*_):
        value=variabile.get().casefold()
        color=TEXT
        if value.startswith(('errore','operazione non riuscita','processo pesca terminato')):
            color=COLORI['danger_text']
        elif value.startswith(('completato 3/3','controllo terminato','disponibile versione')):
            color=GOLD
        elif value.startswith(('in attesa','attesa finestra','solo simulazione','stop')):
            color=MUTED
        label.configure(foreground=color)
    token=variabile.trace_add('write',aggiorna)
    def cleanup(event):
        if event.widget is label:variabile.trace_remove('write',token)
    label.bind('<Destroy>',cleanup,add='+');aggiorna()
    return label

def indicatori_pesca(parent,variabile):
    # Un'unica striscia HUD, senza tre card annidate.
    bar=tk.Frame(parent,bg=COLORI['input'],padx=8,pady=7)
    bar.pack(fill='x',pady=(4,8))
    values=[]
    for index,name in enumerate(('COLPI','CERCHIO','TRACKING')):
        bar.columnconfigure(index,weight=1,uniform='hud')
        box=tk.Frame(bar,bg=COLORI['input'])
        box.grid(row=0,column=index,sticky='ew',padx=(0,8 if index<2 else 0))
        tk.Label(box,text=name,font=FONT['caption'],fg=MUTED,bg=COLORI['input'],
                 anchor='w').pack(fill='x')
        label=tk.Label(box,text='—',font=FONT['status'],fg=TEXT,bg=COLORI['input'],anchor='w')
        label.pack(fill='x',pady=(2,0));values.append(label)
    def update(*_):
        parts=variabile.get().split('·')
        for index,label in enumerate(values):
            value=parts[index].strip() if index<len(parts) else '—'
            for prefix in ('Colpi ','Cerchio ','Tracking '):
                if value.startswith(prefix):value=value[len(prefix):]
            if index==0:value=' / '.join(piece.strip() for piece in value.split('/'))
            color=COLORI['danger_text'] if index==1 and value.upper()=='RED' else TEXT
            label.configure(text=value,fg=color)
    token=variabile.trace_add('write',update)
    def clean(event):
        if event.widget is bar:variabile.trace_remove('write',token)
    bar.bind('<Destroy>',clean,add='+');update()
    return bar


class AnteprimaPesca(AnteprimaTerreno):
    """Presentazione dedicata al formato del minigioco; nessuna elaborazione del tracking."""
    def _draw(self):
        from PIL import Image,ImageTk
        self._pending=None
        w=max(120,self.winfo_width());h=self._preview_height(w,258/285,.48)
        if int(self.cget('height'))!=h:tk.Canvas.configure(self,height=h)
        if self._last==(w,h):return
        self._last=(w,h);self.delete('all')
        self.create_rectangle(0,0,w-1,h-1,outline=COLORI['preview_edge'])
        if self._source is not None:
            iw,ih=self._source.size;factor=min((w-8)/iw,(h-8)/ih)
            size=(max(1,round(iw*factor)),max(1,round(ih*factor)))
            self._photo=ImageTk.PhotoImage(self._source.resize(size,Image.Resampling.BILINEAR))
            self.create_image(w/2,h/2,image=self._photo);return
        self.create_oval(-18,-10,10,10,outline=MUTED,width=2,tags='empty')
        self.create_line(10,-3,20,-11,20,11,10,3,fill=MUTED,width=2,tags='empty')
        self.create_oval(-10,-3,-8,-1,fill=MUTED,outline=MUTED,tags='empty')
        title=self.create_text(0,28,text=self._text,fill=TEXT,font=FONT['subsection_title'],
                               anchor='n',justify='center',width=max(100,w-48),tags='empty')
        bottom=self.bbox(title)[3]
        self.create_text(0,bottom+8,text='La cattura apparirà quando il minigioco sarà rilevato.',
                         fill=MUTED,font=FONT['secondary'],anchor='n',justify='center',
                         width=max(100,w-48),tags='empty')
        x1,y1,x2,y2=self.bbox('empty')
        self.move('empty',w/2-(x1+x2)/2,h/2-(y1+y2)/2)


COMPONENTI=('torch','torchvision','easyocr','mss','pyautogui','cv2','tkinter','PIL.Image','PIL.ImageTk')

def leggi_componenti(report):
    """Solo parsing degli esiti stampati da setup_check; nessuna nuova verifica."""
    result={}
    for line in report.splitlines():
        for name in COMPONENTI:
            if line.startswith(name+': OK'):
                result[name]=(line[len(name+': OK'):].strip() or '—','OK')
            elif line.startswith('MANCANTE/ERRORE '+name+':'):
                result[name]=('—','ERRORE')
    return result


class RiepilogoComponenti(ttk.Frame):
    """Lista compatta degli esiti gia prodotti dalla verifica."""
    def __init__(self,parent):
        super().__init__(parent,style='Card.TFrame');self.pack(fill='x',pady=(4,2))
        self.labels={}
        for column,weight in enumerate((4,3,2)):self.columnconfigure(column,weight=weight,uniform='components')
        for column,title in enumerate(('COMPONENTE','VERSIONE','STATO')):
            ttk.Label(self,text=title,font=FONT['caption'],foreground=MUTED).grid(
                row=0,column=column,sticky='w',padx=(0,12),pady=(0,6))
        for index,name in enumerate(COMPONENTI):
            row=2*index+1
            ttk.Separator(self,orient='horizontal').grid(row=row,column=0,columnspan=3,sticky='ew')
            ttk.Label(self,text=name,font=FONT['body']).grid(row=row+1,column=0,sticky='w',padx=(0,12),pady=2)
            version=ttk.Label(self,text='—',font=FONT['technical'],foreground=MUTED)
            version.grid(row=row+1,column=1,sticky='w',padx=(0,12))
            status=ttk.Label(self,text='●  DA VERIFICARE',font=FONT['caption'],foreground=MUTED)
            status.grid(row=row+1,column=2,sticky='w')
            self.labels[name]=(version,status)
        self._wrap_width=None
        self.bind('<Configure>',self._wrap)
    def _wrap(self,event):
        if event.width==self._wrap_width:return
        self._wrap_width=event.width
        for version,status in self.labels.values():
            version.configure(wraplength=max(70,int(event.width*.30)-12))
            status.configure(wraplength=max(90,int(event.width*.24)-12))
    def mostra(self,report):
        results=leggi_componenti(report)
        if not results:return
        for name,(version,status) in self.labels.items():
            value,state=results.get(name,('—','NON RILEVATO'))
            version.configure(text=value)
            status.configure(text='●  '+state,foreground=COLORI['danger_text'] if state=='ERRORE' else '#96a99b' if state=='OK' else MUTED)


def barra_windows_scura(root):
    """Colora solo la cornice nativa; nessuna sostituzione dei controlli Windows."""
    import sys
    if sys.platform!='win32':return
    import ctypes
    from ctypes import wintypes
    try:
        user=ctypes.WinDLL('user32',use_last_error=True)
        dwm=ctypes.WinDLL('dwmapi',use_last_error=True)
        user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
        user.GetAncestor.restype=wintypes.HWND
        dwm.DwmSetWindowAttribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
        dwm.DwmSetWindowAttribute.restype=ctypes.c_long
        user.SystemParametersInfoW.argtypes=[wintypes.UINT,wintypes.UINT,ctypes.c_void_p,wintypes.UINT]
        user.SystemParametersInfoW.restype=wintypes.BOOL
        class HIGHCONTRAST(ctypes.Structure):
            _fields_=[('cbSize',wintypes.UINT),('dwFlags',wintypes.DWORD),('scheme',wintypes.LPWSTR)]
        build=sys.getwindowsversion().build
    except (OSError,AttributeError):
        return
    applied=set()
    def apply(event=None):
        if event is not None and event.widget is not root:return
        try:
            if not root.winfo_exists() or not root.winfo_ismapped():return
            hwnd=user.GetAncestor(root.winfo_id(),2)  # GA_ROOT: cornice esterna di Tk.
            if not hwnd or hwnd in applied:return
            hc=HIGHCONTRAST();hc.cbSize=ctypes.sizeof(hc)
            if user.SystemParametersInfoW(0x42,hc.cbSize,ctypes.byref(hc),0) and hc.dwFlags&1:
                return  # Conserva il tema accessibile scelto dall'utente.
            def attribute(number,value):
                return dwm.DwmSetWindowAttribute(hwnd,number,ctypes.byref(value),ctypes.sizeof(value))>=0
            if build>=17763:
                ok=attribute(20,wintypes.BOOL(1))
                if not ok and build<22000:attribute(19,wintypes.BOOL(1))
            if build>=22000:
                def color(hex_value):
                    r,g,b=(int(hex_value[i:i+2],16) for i in (1,3,5))
                    return wintypes.DWORD(r|(g<<8)|(b<<16))
                attribute(35,color(BG))       # DWMWA_CAPTION_COLOR
                attribute(36,color(MUTED))    # DWMWA_TEXT_COLOR
                attribute(34,color(BORDER))   # DWMWA_BORDER_COLOR
            applied.add(hwnd)
        except (OSError,AttributeError,tk.TclError):
            pass  # Una personalizzazione non disponibile non impedisce l'avvio.
    root.bind('<Map>',apply,add='+')
    root.after_idle(apply)

class ColonneImpostazioni(Colonne):
    """Stessi breakpoint e ordine; colonne superiori di uguale ampiezza."""
    def _layout(self,event):
        previous=self._wide
        super()._layout(event)
        if previous!=self._wide:
            self.columnconfigure(0,weight=1,uniform='colonne')
            self.columnconfigure(1,weight=1 if self._wide else 0,
                                 uniform='colonne' if self._wide else '')
