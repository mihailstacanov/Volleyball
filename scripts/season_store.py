"""Local, versioned season archive. No network requests.

Historical JSON files are authoritative. HTML contains embedded copies for
standalone/offline-friendly rendering. Current snapshots are stored by season,
and no command overwrites a different year's snapshot.
"""
import argparse
import json
import re
from pathlib import Path

ROOT=Path("data")
TEAM1="SG Poing I"
TEAM2="SG Poing II"
SEASON=2026
SOURCES={TEAM1:"https://www.ost.volleyball-freizeit.de/saison/1096",
         TEAM2:"https://www.ost.volleyball-freizeit.de/saison/1106"}
HIST_RE=re.compile(r"const histRaw=(\[\[.*?\]\]), seasonRows=(\[\[.*?\]\]);",re.S)
DATA_RE=re.compile(r"const TEAM2_DATA=(.*?);\nconst teams=",re.S)
CURRENT_RE=re.compile(r"const teams=(\[.*?\]), games=(\[\[.*?\]\]), poing=(\d+), stats=(\[\[.*?\]\]);",re.S)
ARCH_RE=re.compile(r'(<h2 class="sectionhead" id="archiv">.*?<tbody>)(.*?)(</tbody>)',re.S)

def require(ok,msg):
    if not ok: raise RuntimeError(msg)

def encode(data):
    return json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("<","\\u003c")

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and read(path)==data: return
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def season_of(d):
    return int(d[:4])-(int(d[5:7])<7)

def team_key(path):
    return "team2" if Path(path).name=="team2.html" else "team1"

def history_path(path):
    return ROOT/"history"/(team_key(path)+".json")

def snapshot_path(path,year=SEASON):
    return ROOT/"seasons"/f"{year}-{str(year+1)[-2:]}"/(team_key(path)+".json")

def historical_html(path,s):
    key=team_key(path)
    h=read(history_path(path))
    require(h["schema"]==1 and h["team"]==(TEAM2 if key=="team2" else TEAM1),"Wrong archive identity")
    if key=="team1":
        m=HIST_RE.search(s); a=ARCH_RE.search(s)
        require(m and a,"Missing Team I history markers")
        history,seasons=map(json.loads,m.groups())
        rows=re.findall(r"<tr>.*?</tr>",a[2],re.S)
        require(rows and seasons and seasons[0][0]==f"{SEASON}/{str(SEASON+1)[-2:]}","Invalid current season")
        require(all(season_of(x[0])<SEASON for x in h["matches"]),"Archive contains current/future match")
        require(len(h["seasonRows"])==len(h["archiveRows"]),"Archive table incomplete")
        own=[x for x in history if season_of(x[0])==SEASON]
        new="const histRaw="+encode(h["matches"]+own)+", seasonRows="+encode([seasons[0]]+h["seasonRows"])+";"
        s=HIST_RE.sub(lambda _:new,s,count=1)
        s=ARCH_RE.sub(lambda a:a[1]+rows[0]+"".join(h["archiveRows"])+a[3],s,count=1)
    else:
        m=DATA_RE.search(s); require(m,"Missing Team II history marker")
        d=json.loads(m[1])
        require(all(x["year"]<SEASON for x in h["archive"]) and all(x[0]<SEASON for x in h["hist"]),"Archive contains current/future match")
        for name in ("archive","hist","archiveNote","archiveScanned"): d[name]=h[name]
        s=DATA_RE.sub(lambda _: "const TEAM2_DATA="+encode(d)+";\nconst teams=",s,count=1)
    return s

def restore(path):
    s=path.read_text(encoding="utf-8")
    updated=historical_html(path,s)
    if s!=updated: path.write_text(updated,encoding="utf-8")

def current(path):
    s=path.read_text(encoding="utf-8")
    if team_key(path)=="team1":
        m=CURRENT_RE.search(s); hist=HIST_RE.search(s); a=ARCH_RE.search(s)
        require(m and hist and a,"Missing Team I snapshot data")
        names,games=json.loads(m[1]),json.loads(m[2])
        rows=re.findall(r"<tr>.*?</tr>",a[2],re.S)
        d=dict(schema=1,team=TEAM1,season=SEASON,source=SOURCES[TEAM1],
            stamp=re.search(r"Datenstand ([^<]+)",s)[1],names=names,games=games,stats=json.loads(m[4]),
            own=[x for x in json.loads(hist[1]) if season_of(x[0])==SEASON],
            seasonRow=json.loads(hist[2])[0],archiveRow=rows[0])
    else:
        m=DATA_RE.search(s);require(m,"Missing Team II snapshot data")
        t=json.loads(m[1])
        d=dict(schema=1,team=TEAM2,season=SEASON,source=SOURCES[TEAM2],
            **{k:t[k] for k in ("stamp","names","games","table","own")})
    d["complete"]=all(x[4] is not None for x in d["games"])
    return d

def snapshot(path,fixtures=None,table=None,source_names=None):
    d=current(path)
    target=snapshot_path(path)
    old=read(target) if target.exists() else None
    if old:
        require(old["team"]==d["team"] and old["season"]==d["season"],"Snapshot identity mismatch")
        old_results={(old["names"][m[0]],old["names"][m[1]]):m[4] for m in old["games"] if m[4] is not None}
        new_results={(d["names"][m[0]],d["names"][m[1]]):m[4] for m in d["games"] if m[4] is not None}
        require(old_results.keys()<=new_results.keys(),"Snapshot would lose completed matches")
    if fixtures is not None:
        require(table is not None and source_names is not None,"Missing full league snapshot")
        d["leagueMatches"]=[dict(home=source_names[m[0]],away=source_names[m[1]],date=m[2],time=m[3],score=m[4],sets=sets) for m,sets in sorted(fixtures.values(),key=lambda v:(v[0][2] or "9999",v[0][3],source_names[v[0][0]],source_names[v[0][1]]))]
        d["leagueStandings"]=[dict(team=source_names[i],rank=t[0],points=t[1],wins=t[2],setsFor=t[3],setsAgainst=t[4],ballsFor=t[5],ballsAgainst=t[6],games=t[7]) for i,t in sorted(table.items(),key=lambda v:v[1][0])]
    elif old:
        # A render-only run never erases richer data previously collected.
        for k in ("leagueMatches","leagueStandings"):
            if k in old: d[k]=old[k]
        require(all(old.get(k)==d.get(k) for k in ("names","games","stats","table")) or "leagueMatches" not in old,"Changed league requires fresh validated details")
    write(target,d)
    print("Saved season snapshot:",target,"complete:",d["complete"],flush=True)

def verify(path):
    s=path.read_text(encoding="utf-8")
    # Compare parsed values, not insignificant JSON whitespace.
    regenerated=historical_html(path,s)
    if team_key(path)=="team1":
        require(HIST_RE.search(s).groups() and [json.loads(x) for x in HIST_RE.search(s).groups()]==[json.loads(x) for x in HIST_RE.search(regenerated).groups()],"Team I historical data mismatch")
        require(ARCH_RE.search(s)[2]==ARCH_RE.search(regenerated)[2],"Team I archive table mismatch")
    else:
        require(json.loads(DATA_RE.search(s)[1])==json.loads(DATA_RE.search(regenerated)[1]),"Team II historical data mismatch")
    saved=read(snapshot_path(path)); now=current(path)
    require(all(saved.get(k)==v for k,v in now.items()),"Current season snapshot mismatch: "+str(path))
    print("Local archive and snapshot verified:",path,flush=True)


def prepare_rollover(year):
    """Create next-season history inputs from the stored snapshots, without touching active HTML."""
    target=ROOT/"rollover"/f"{year+1}-{str(year+2)[-2:]}"
    updates=[]
    for path in (Path("index.html"),Path("team2.html")):
        h=read(history_path(path))
        d=read(snapshot_path(path,year))
        require(d["season"]==year and d["team"]==h["team"],"Wrong rollover snapshot")
        require(d["complete"],"Season is not fully recorded; do not label it complete")
        if team_key(path)=="team1":
            require(all(season_of(m[0])<year for m in h["matches"]),"History already includes this season")
            row=d["seasonRow"][:];row[-1]="—"
            h["seasonRows"]=[row]+h["seasonRows"]
            h["archiveRows"]=[d["archiveRow"].replace("<td>Laufend</td>","<td>—</td>")]+h["archiveRows"]
            h["matches"]+=d["own"]
        else:
            require(all(x["year"]<year for x in h["archive"]),"History already includes this season")
            i=d["names"].index(TEAM2)
            rank,p,w,sw,sl,bp,ba,g=d["table"][i]
            h["archive"]=[dict(year=year,name=TEAM2,id=d["source"].rsplit("/",1)[-1],rank=rank,n=len(d["names"]),p=p,w=w,sw=sw,sl=sl,bp=bp,ba=ba,g=g)]+h["archive"]
            h["hist"]+=d["own"]
            h["archiveNote"]+=" Ab "+str(year)+"/"+str(year+1)[-2:]+": abgeschlossene Saison aus lokalem Snapshot übernommen."
        updates.append((target/(team_key(path)+".json"),h))
    for path,h in updates: write(path,h)
    print("Prepared next-season archives:",target,flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=("restore","snapshot","verify","prepare-rollover"))
    p.add_argument("pages",nargs="*",default=[])
    p.add_argument("--year",type=int,default=SEASON)
    args=p.parse_args()
    if args.command=="prepare-rollover":
        prepare_rollover(args.year)
        return
    for file in args.pages or ["index.html","team2.html"]:
        path=Path(file)
        {"restore":restore,"snapshot":snapshot,"verify":verify}[args.command](path)
if __name__=="__main__":main()
