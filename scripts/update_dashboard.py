"""Refresh the current 2026/27 season; fail closed on inconsistent or missing data."""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.request import Request, urlopen
from html import escape
from bs4 import BeautifulSoup

URL="https://www.ost.volleyball-freizeit.de/saison/1096"
PATH=Path("index.html")
NOW=datetime.now(ZoneInfo("Europe/Berlin"))
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def extract(s,p):
    m=re.search(p,s,re.S)
    require(m,"Missing dashboard data marker: "+p)
    return json.loads(m[1])
def replace(s,p,v):
    s,n=re.subn(p,lambda m:v(m) if callable(v) else v,s,count=1,flags=re.S)
    require(n==1,"Missing dashboard template: "+p)
    return s
def js(v): return json.dumps(v,ensure_ascii=False,separators=(",",":"))
def pct(a,b): return (f"{100*a/b:.1f}".replace(".",",")+" %") if b else "—"
def date(d): return datetime.fromisoformat(d).strftime("%d.%m.%Y")
def pair(s): return tuple(int(x.strip()) for x in s.split(":"))
def won(m): return sum(a>b for a,b in m[3])
def parse(soup,names):
    fixtures={}; table={}; row_count=0; examples=[]
    def norm(x): return " ".join(x.split())
    def team(cell):
        candidates=[norm(cell.get_text(" ",strip=True))]
        candidates.extend(norm(x.get_text(" ",strip=True)) for x in cell.find_all(["a","span","strong"]))
        candidates.extend(norm(str(x.get("alt",""))) for x in cell.find_all("img"))
        exact={name for name in names if name in candidates}
        if len(exact)==1: return next(iter(exact))
        if not exact:
            text=candidates[0]
            hits=[name for name in names if re.search(r"(?<!\w)"+re.escape(name)+r"(?!\w)",text)]
            if len(hits)==1: return hits[0]
        return None
    def store(target,key,value):
        require(key not in target or target[key]==value,"Conflicting duplicate row: "+str(key))
        target[key]=value
    def numbers(cells):
        out=[]
        for x in cells:
            if re.fullmatch(r"\d+",x): out.append(int(x))
            elif re.fullmatch(r"\d+\s*:\s*\d+",x): out.extend(pair(x))
        return out
    for tr in soup.find_all("tr"):
        cells=tr.find_all(["td","th"],recursive=False)
        if not cells: continue
        row_count+=1
        c=[norm(x.get_text(" ",strip=True)) for x in cells]
        tags=[team(x) for x in cells]
        ix=[i for i,x in enumerate(tags) if x is not None]
        if ix and len(examples)<5: examples.append(c)
        if len(ix)==2:
            a,b=ix
            prefix=" ".join(c[:a])
            ds=re.findall(r"(?<!\d)(\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2}))(?!\d)",prefix)
            ts=re.findall(r"(?<!\d)(\d{1,2}:[0-5]\d)(?!\d)",prefix)
            if not ds: continue
            require(len(ds)==1 and len(ts)==1,"Ambiguous fixture date/time: "+repr(c))
            d=datetime.strptime(ds[0],"%d.%m.%Y" if len(ds[0].split(".")[-1])==4 else "%d.%m.%y").date().isoformat()
            t=datetime.strptime(ts[0],"%H:%M").strftime("%H:%M")
            require("2026-07-01"<=d<"2027-07-01","Wrong season")
            h,v=names.index(tags[a]),names.index(tags[b])
            require(h!=v,"Self fixture")
            tail=c[b+1:]
            vals=numbers(tail)
            if not vals:
                # Only accept an empty score or explicit placeholders, not an unparsed result.
                require(not any(re.search(r"\d",x) for x in tail),"Unrecognized result: "+repr(tail))
                score=None; sets=[]
            else:
                require(len(vals)==12,"Expected twelve result values: "+repr(tail))
                sets=[vals[i:i+2] for i in (6,8,10)]
                score=sum(x>y for x,y in sets)
                require(all(x!=y for x,y in sets) and vals[:4]==[score,3-score,score,3-score] and vals[4:6]==[sum(x for x,y in sets),sum(y for x,y in sets)],"Inconsistent match score")
            store(fixtures,(h,v),([h,v,d,t,score],sets))
        elif len(ix)==1:
            i=ix[0]
            before=numbers(c[:i])
            # Standings contain hidden numeric sort keys before the displayed ratios.
            # Extract only the trailing a:b pair in each score cell.
            after=[]
            for cell in c[i+1:]:
                m=re.search(r"(\d+)\s*:\s*(\d+)$",cell)
                if m: after.extend(map(int,m.groups()))
                elif re.fullmatch(r"\d+",cell): after.append(int(cell))
            if len(before)!=1 or len(after)!=7: continue
            rank=before[0]; p,w,sw,sl,bp,ba,g=after
            key=names.index(tags[i])
            store(table,key,(rank,p,w,sw,sl,bp,ba,g))
    print(f"League HTML: {row_count} rows, {len(fixtures)} fixtures, {len(table)} standings",flush=True)
    if len(fixtures)!=len(names)*(len(names)-1) or len(table)!=len(names):
        print("Example recognized rows:",repr(examples)[:2500],flush=True)
        if not examples:
            print("First table rows:",repr([norm(x.get_text(" ",strip=True))[:200] for x in soup.find_all("tr")[:8]]),flush=True)
    require(set(fixtures)=={(h,v) for h in range(len(names)) for v in range(len(names)) if h!=v},f"Incomplete fixture list: {len(fixtures)} of {len(names)*(len(names)-1)}")
    require(len(table)==len(names) and sorted(x[0] for x in table.values())==list(range(1,len(names)+1)),"Incomplete standings")
    for i in range(len(names)):
        played=[(m,st) for m,st in fixtures.values() if i in m[:2] and m[4] is not None]
        ss=[xy if m[0]==i else xy[::-1] for m,st in played for xy in st]
        sw=sum(a>b for a,b in ss); sl=len(ss)-sw
        w=sum((m[4] if m[0]==i else 3-m[4])>=2 for m,st in played)
        rank,p,ww,x,y,bp,ba,g=table[i]
        require((p,ww,x,y,bp,ba,g)==(sw,w,sw,sl,sum(a for a,b in ss),sum(b for a,b in ss),len(played)),"Official totals disagree: "+names[i])
    return fixtures,table

def fetch_source(names):
    errors=[]
    for url in (URL,"https://www.ost.volleyball-freizeit.de/schedule/overview/1096"):
        try:
            req=Request(url,headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36","Accept":"text/html,application/xhtml+xml","Accept-Language":"de-DE,de;q=0.9","Cache-Control":"no-cache"})
            with urlopen(req,timeout=35) as response:
                require(response.status==200,"League HTTP error")
                raw=response.read(4_000_001)
                print("League response:",response.geturl(),len(raw),"bytes",flush=True)
            require(len(raw)<=4_000_000,"Source too large")
            soup=BeautifulSoup(raw,"html5lib")
            print("League title:",soup.title.get_text(" ",strip=True) if soup.title else "(none)",flush=True)
            return parse(soup,names)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            print("Source rejected:",errors[-1],flush=True)
    raise RuntimeError("No complete, consistent league source: "+" | ".join(errors))

def main():
    s=PATH.read_text(encoding="utf-8")
    names0=extract(s,r"const teams=(\[.*?\]), games=")
    games0=extract(s,r"games=(\[\[.*?\]\]), poing=")
    hist0=extract(s,r"const histRaw=(\[\[.*?\]\]), seasonRows=")
    seasons0=extract(s,r"seasonRows=(\[\[.*?\]\]);")
    stats0=extract(s,r"stats=(\[\[.*?\]\]);")
    require(NOW.date().isoformat()<"2027-07-01","Season ended: review new league ID and halls first")
    matches,table=fetch_source(names0)
    old={(m[0],m[1]):m for m in games0}
    require(set(old)==set(matches),"Fixture identities changed")
    for key,(m,st) in matches.items():
        require(old[key][4] is None or m[4] is not None,"Source lost existing result; possibly stale")
        require(m[4] is None or m[2]<=NOW.date().isoformat(),"Future result")
    order=sorted(table,key=lambda i:table[i][0]); names=[names0[i] for i in order]
    poing=names.index("SG Poing I"); oldpoing=names0.index("SG Poing I")
    stats=[[table[i][1],table[i][2],table[i][7]] for i in order]
    games=[]; own=[]
    for m,st in matches.values():
        h,v,d,t,score=m
        games.append([order.index(h),order.index(v),d,t,score])
        if score is not None and oldpoing in (h,v):
            home=h==oldpoing
            own.append([d,"H" if home else "A",names0[v if home else h],st if home else [xy[::-1] for xy in st]])
    sortkey=lambda m:(m[2],m[3],m[0],m[1])
    games.sort(key=sortkey); own.sort()
    hist=[m for m in hist0 if m[0]<"2026-07-01"]+own
    rank,points,w,sw,sl,bp,ba,g=table[oldpoing]; n=len(names)
    require(g==len(own),"Missing Poing match details")
    seasons=[["2026/27",f"{rank} / {n}",g,w,"Laufend"]]+seasons0[1:]
    if names==names0 and sorted(games0,key=sortkey)==games and hist0==hist and stats0==stats and seasons0==seasons:
        print("No changed league data."); return
    s=replace(s,r"const teams=\[.*?\], games=\[\[.*?\]\], poing=\d+, stats=\[\[.*?\]\];",f"const teams={js(names)}, games={js(games)}, poing={poing}, stats={js(stats)};")
    s=replace(s,r"const histRaw=\[\[.*?\]\], seasonRows=\[\[.*?\]\];",f"const histRaw={js(hist)}, seasonRows={js(seasons)};")
    def kpi(label,value,sub):
        return f'<div class="kpi"><span>{label}</span><strong>{value}</strong><small>{sub}</small></div>'
    overview=kpi("Tabellenplatz",f"{rank} / {n}","Aktueller Ligastand")+kpi("Siege",f"{w} / {g}",pct(w,g)+" Siegquote")+kpi("Ligapunkte",points,f"{points} von {g*3} möglichen")+kpi("Satzbilanz",f"{sw} : {sl}",f"Ballpunkte {bp} : {ba}")
    s=replace(s,r'(<h2 class="sectionhead" id="aktuell">.*?</h2><div class="kpis">).*?(</div><div class="twocol">)',lambda m:m[1]+overview+m[2])
    tablehtml=""
    for i in order:
        rr,p,ww,x,y,bb,aa,gg=table[i]
        cl="ours" if i==oldpoing else ""
        tablehtml+=f'<tr class="{cl}"><td>{rr}</td><td>{escape(names0[i])}</td><td>{p}</td><td>{ww}</td><td>{gg}</td><td>{x}:{y}</td></tr>'
    s=replace(s,r'(<h2>Ligatabelle</h2>.*?<tbody>).*?(</tbody>)',lambda m:m[1]+tablehtml+m[2])
    pending=[m for m in games if poing in m[:2] and m[4] is None]
    fixtures="".join(f'<div class="fixture"><span class="pill">{"Heimspiel" if m[0]==poing else "Auswärts"}</span><strong>{escape(names[m[0]])} – {escape(names[m[1]])}</strong><small>{date(m[2])} · {m[3]} Uhr</small></div>' for m in pending[:2]) or "<p>Keine offenen Spiele.</p>"
    s=replace(s,r'(<div class="next">).*?(</div><p style="margin-top:15px">)',lambda m:m[1]+fixtures+m[2])
    rows=""
    for m in reversed(own[-5:]):
        d,h,o,st=m; v=won(m); cl="win" if v>=2 else "loss"; place="Heim" if h=="H" else "Auswärts"; scores=" · ".join(f"{a}:{b}" for a,b in st)
        rows+=f'<tr><td>{date(d)}</td><td>{escape(o)}</td><td>{place}</td><td class="{cl}">{v}:{3-v}</td><td>{scores}</td></tr>'
    s=replace(s,r'(<h2>Letzte Ergebnisse</h2>.*?<tbody>).*?(</tbody>)',lambda m:m[1]+rows+m[2])
    def split(label,h):
        v=[m for m in own if m[1]==h]; ss=[xy for m in v for xy in m[3]]; a=sum(x>y for x,y in ss)
        return kpi(label,f"{sum(won(m)>=2 for m in v)} / {len(v)}",f"{a}:{len(ss)-a} Sätze · {sum(x for x,y in ss)}:{sum(y for x,y in ss)} Bälle")
    close=[m for m in own if won(m) in (1,2)]
    analysis=split("Heimbilanz","H")+split("Auswärtsbilanz","A")+kpi("Ballpunktquote",pct(bp,bp+ba),f"{bp} von {bp+ba} Ballpunkten")+kpi("Enge Spiele (2:1 / 1:2)",f"{len(close)} / {g}",f"Davon {sum(won(m)==2 for m in close)} Siege")
    stamp=NOW.strftime("%d.%m.%Y")
    s=replace(s,r'(<h2 class="sectionhead" id="analyse">.*?</h2>\s*<p class="muted">).*?(</p>\s*<div class="kpis">).*?(</div>\s*<div class="twocol">)',lambda m:m[1]+f"{g} ausgewertete Spiele · alle drei Sätze werden gespielt · Momentaufnahme vom {stamp}."+m[2]+analysis+m[3])
    form="".join(f'<span class="form{"win" if won(m)>=2 else "loss"}">{"S" if won(m)>=2 else "N"}<br/>{won(m)}:{3-won(m)}</span>' for m in own[-5:])
    s=replace(s,r'(<div class="formstrip">).*?(</div><p class="muted">).*?(</p>)',lambda m:m[1]+form+m[2]+"Chronologisch · letzte fünf Spiele."+m[3])
    s=replace(s,r'(<div id="diffchart"></div><p class="muted">).*?(</p>)',lambda m:m[1]+"Ballpunktedifferenz aus den erfassten Saisonspielen."+m[2])
    diffs=[[date(m[0])[:6],sum(a-b for a,b in m[3])] for m in own]; scale=max([abs(x[1]) for x in diffs]+[1])
    s=replace(s,r"const diffs=\[.*?\];",f"const diffs={js(diffs)};")
    s=re.sub(r"Math\.abs\(n\)/\d+\*50",f"Math.abs(n)/{scale}*50",s)
    setwins=[sum(m[3][i][0]>m[3][i][1] for m in own) for i in range(3)]
    s=replace(s,r"const currentSetWins=\[.*?\];const currentPlayed=\d+;",f"const currentSetWins={js(setwins)};const currentPlayed={g};")
    weak=min(range(3),key=lambda i:setwins[i])+1
    s=replace(s,r'(<div id="setchart"></div><p>).*?(</p>)',lambda m:m[1]+f"<strong>Ansatzpunkt: Satz {weak}.</strong> Gewonnene Sätze: "+", ".join(f"Satz {i+1}: {x}/{g}" for i,x in enumerate(setwins))+"."+m[2])
    nxt="Keine offenen Spiele." if not pending else f"{escape(names[pending[0][1] if pending[0][0]==poing else pending[0][0]])} am {date(pending[0][2])}."
    s=replace(s,r'<p><strong>Nächster Gegner:</strong>.*?</p>',f"<p><strong>Nächster Gegner:</strong> {nxt}</p>")
    vals=iter([(100*w/g if g else 0,pct(w,g)),(100*(n-rank)/(n-1),f"{rank}. von {n}"),(100*sw/(sw+sl) if sw+sl else 0,pct(sw,sw+sl))])
    def chart(m):
        x,label=next(vals)
        return m[1]+f"{x:.2f}%"+m[2]+label+m[3]
    s,count=re.subn(r'(<div class="chartrow"><span>26/27</span><div class="track"><div class="bar new ongoing" style="width:)[\d.]+%("></div></div><span class="chartval">).*?(</span></div>)',chart,s)
    require(count==3,"Season chart markers changed")
    archive=f'<td>SG Poing I</td><td>{rank} / {n}</td><td>{g}</td><td>{w}</td><td>{g-w}</td><td>{pct(w,g)}</td><td>{points}</td><td>{sw}:{sl}</td><td>{bp}:{ba}</td><td>Laufend</td>'
    s=replace(s,r'(>2026/27</a></td>)<td>SG Poing I</td>.*?(</tr>)',lambda m:m[1]+archive+m[2])
    s=replace(s,r"Detailanalyse: alle \d+ Spiele aus 2022/23 bis 2026/27 \(Stand \d{2}\.\d{2}\.\d{4}\)",f"Detailanalyse: alle {len(hist)} Spiele aus 2022/23 bis 2026/27 (Stand {stamp})")
    stamp_with_time=NOW.strftime("%d.%m.%Y · %H:%M Uhr")
    s=replace(s,r"Datenstand \d{2}\.\d{2}\.\d{4}(?: · (?:\d{2}:\d{2} Uhr|Uhrzeit nicht erfasst))?",f"Datenstand {stamp_with_time}")
    s=replace(s,r"(Offizielle Ligadaten</a> · Stand )\d{2}\.\d{2}\.\d{4}",lambda m:m[1]+stamp)
    s=re.sub(r"DTSTAMP:\d{8}T\d{6}Z","DTSTAMP:"+datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ"),s)
    require(all(x in s for x in ('id="calbody"','id="dashrefresh"','id="hallenkarte"','id="installapp"','id="dashmenutoggle"','id="adminrefresh"')),"Existing features lost")
    PATH.write_text(s,encoding="utf-8")
    print(f"Validated {len(games)} fixtures, {g} Poing results, rank {rank}/{n}.")
def self_test():
    import tempfile
    from unittest.mock import patch
    global PATH
    original=PATH
    source=original.read_text(encoding="utf-8")
    names=extract(source,r"const teams=(\[.*?\]), games=")
    games=extract(source,r"games=(\[\[.*?\]\]), poing=")
    hist=extract(source,r"const histRaw=(\[\[.*?\]\]), seasonRows=")
    own=names.index("SG Poing I")
    scores={(m[0],m[1],m[2]):m[3] for m in hist if m[0]>="2026-07-01"}
    sums=[[0]*7 for _ in names]
    rows=[]
    moved=False
    for h,v,d,t,score in games:
        if score is None and not moved:
            t="20:01" if t!="20:01" else "20:02"
            moved=True
        values=[]
        if score is not None:
            if own in (h,v):
                st=scores[(d,"H" if h==own else "A",names[v if h==own else h])]
                if v==own: st=[xy[::-1] for xy in st]
            else:
                st=[[25,19]]*score+[[19,25]]*(3-score)
            values=[score,3-score,score,3-score,sum(x for x,y in st),sum(y for x,y in st)]+[x for xy in st for x in xy]
            for i,a,b,ss in ((h,score,3-score,st),(v,3-score,score,[xy[::-1] for xy in st])):
                z=sums[i]; z[0]+=a; z[1]+=int(a>=2); z[2]+=a; z[3]+=b; z[4]+=sum(x for x,y in ss); z[5]+=sum(y for x,y in ss); z[6]+=1
        # Include TH, non-breaking spaces, separate logo cells, and nested names.
        rows.append("<tr><th>1</th><td>"+date(d)+"</td><td>"+t+"</td><td><a>"+escape(names[h])+"</a></td><td></td><td><span>"+escape(names[v])+"</span></td>"+"".join("<td>"+str(x)+"</td>" for x in values or [""]*12)+"</tr>")
    standing=[]
    for i,z in enumerate(sums):
        p,w,sw,sl,bp,ba,g=z
        standing.append(f'<tr><th>{i+1}</th><td></td><td><a>{escape(names[i])}</a></td><td></td><td>{p}</td><td>{w}</td><td><span style="display:none">14</span> {sw}&nbsp;:&nbsp;{sl}</td><td><span style="display:none">1.36496350365</span> {bp}:{ba}</td><td>{g}</td></tr>')
    data=parse(BeautifulSoup("<table>"+"".join(standing+rows)+"</table>","html5lib"),names)
    require(len(data[0])==len(games),"Parser regression")
    with tempfile.TemporaryDirectory() as tmp:
        PATH=Path(tmp)/"index.html"
        PATH.write_text(source,encoding="utf-8")
        try:
            with patch(__name__+".fetch_source",return_value=data):
                main()
                updated=PATH.read_text(encoding="utf-8")
                require(updated!=source,"Render regression: no update")
                main()
                require(PATH.read_text(encoding="utf-8")==updated,"Render regression: not idempotent")
        finally:
            PATH=original
    print("Synthetic parser and dashboard update regression tests passed.",flush=True)

if __name__=="__main__":
    import sys
    if "--self-test" in sys.argv:
        self_test()
    elif "--check" in sys.argv:
        import tempfile
        original=PATH
        with tempfile.TemporaryDirectory() as tmp:
            PATH=Path(tmp)/"index.html"
            PATH.write_bytes(original.read_bytes())
            main()
            print("Live dry run completed; repository unchanged.")
    else:
        main()
