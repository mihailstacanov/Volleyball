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
    fixtures={}; table={}
    for tr in soup.find_all("tr"):
        c=[" ".join(x.get_text(" ",strip=True).split()) for x in tr.find_all("td",recursive=False)]
        ix=[i for i,x in enumerate(c) if x in names]
        if len(ix)==2:
            a,b=ix
            ds=[i for i,x in enumerate(c[:a]) if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}",x)]
            if not ds: continue
            require(len(ds)==1 and b==a+1,"Unexpected match layout")
            di=ds[0]; d=datetime.strptime(c[di],"%d.%m.%Y").date().isoformat(); t=c[di+1]
            require("2026-07-01"<=d<"2027-07-01" and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",t),"Wrong season or missing time")
            h,v=names.index(c[a]),names.index(c[b])
            require(h!=v and (h,v) not in fixtures,"Duplicate fixture")
            tail=c[b+1:b+13]
            require(len(tail)==12,"Unexpected result columns")
            if all(x in ("","–","-","—") for x in tail): score=None; sets=[]
            else:
                require(all(re.fullmatch(r"\d+",x) for x in tail),"Partial/nonstandard result")
                vals=list(map(int,tail))
                sets=[vals[i:i+2] for i in (6,8,10)]
                score=sum(x>y for x,y in sets)
                require(all(x!=y for x,y in sets) and vals[:4]==[score,3-score,score,3-score] and vals[4:6]==[sum(x for x,y in sets),sum(y for x,y in sets)],"Inconsistent match score")
            fixtures[h,v]=([h,v,d,t,score],sets)
        elif len(ix)==1:
            i=ix[0]
            before=[x for x in c[:i] if re.fullmatch(r"\d+",x)]
            after=[x for x in c[i+1:] if re.fullmatch(r"\d+|\d+\s*:\s*\d+",x)]
            if len(before)!=1 or len(after)!=5 or ":" not in after[2] or ":" not in after[3]: continue
            rank=int(before[0]); p,w=int(after[0]),int(after[1]); sw,sl=pair(after[2]); bp,ba=pair(after[3]); g=int(after[4])
            key=names.index(c[i])
            require(key not in table,"Duplicate standings")
            table[key]=(rank,p,w,sw,sl,bp,ba,g)
    require(len(fixtures)==len(names)*(len(names)-1),"Incomplete fixture list")
    require(len(table)==len(names) and sorted(x[0] for x in table.values())==list(range(1,len(names)+1)),"Incomplete standings")
    for i in range(len(names)):
        played=[(m,st) for m,st in fixtures.values() if i in m[:2] and m[4] is not None]
        ss=[xy if m[0]==i else xy[::-1] for m,st in played for xy in st]
        sw=sum(a>b for a,b in ss); sl=len(ss)-sw
        w=sum((m[4] if m[0]==i else 3-m[4])>=2 for m,st in played)
        rank,p,ww,x,y,bp,ba,g=table[i]
        require((p,ww,x,y,bp,ba,g)==(sw,w,sw,sl,sum(a for a,b in ss),sum(b for a,b in ss),len(played)),"Official totals disagree: "+names[i])
    return fixtures,table
def main():
    s=PATH.read_text(encoding="utf-8")
    names0=extract(s,r"const teams=(\[.*?\]), games=")
    games0=extract(s,r"games=(\[\[.*?\]\]), poing=")
    hist0=extract(s,r"const histRaw=(\[\[.*?\]\]), seasonRows=")
    seasons0=extract(s,r"seasonRows=(\[\[.*?\]\]);")
    stats0=extract(s,r"stats=(\[\[.*?\]\]);")
    require(NOW.date().isoformat()<"2027-07-01","Season ended: review new league ID and halls first")
    req=Request(URL,headers={"User-Agent":"SG-Poing-Volleyball-Dashboard/1.0","Cache-Control":"no-cache"})
    with urlopen(req,timeout=40) as response:
        require(response.status==200,"League HTTP error")
        raw=response.read(4_000_001)
    require(len(raw)<=4_000_000,"Source too large")
    matches,table=parse(BeautifulSoup(raw,"html.parser"),names0)
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
if __name__=="__main__":
    main()
