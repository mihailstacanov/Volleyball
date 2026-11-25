"""Refresh only the current SG Poing II league; use the local historical archive."""
import json, re, sys, time
from urllib.error import URLError, HTTPError
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from update_dashboard import parse, require

ROOT="https://www.ost.volleyball-freizeit.de"
PATH=Path("team2.html")
TEAM="SG Poing II"
NOW=datetime.now(ZoneInfo("Europe/Berlin"))
MARK=re.compile(r"const TEAM2_DATA=(.*?);\nconst teams=",re.S)

def load(url):
    for attempt in range(2):
        try:
            with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html","Accept-Language":"de-DE,de;q=0.9","Cache-Control":"no-cache"}),timeout=15) as r:
                raw=r.read(4000001)
            require(len(raw)<=4000000,"HTML too large")
            return BeautifulSoup(raw,"html5lib")
        except (URLError, TimeoutError, OSError) as e:
            if isinstance(e,HTTPError) and e.code not in (408,429,500,502,503,504): raise
            if attempt==1: raise
            print("Temporary source error; retrying once:",url,str(e),flush=True)
            time.sleep(2)

def read_page():
    s=PATH.read_text(encoding="utf-8")
    m=MARK.search(s);require(m,"Missing Team II data marker")
    return s,m,json.loads(m[1])

def check_seed(data):
    n=len(data["names"]);require(n==7 and TEAM in data["names"],"Wrong Team II division")
    require({(a,b) for a,b,d,t,v in data["games"]}=={(a,b) for a in range(n) for b in range(n) if a!=b},"Incomplete Team II fixtures")
    for i,row in enumerate(data["table"]):
        scored=[v if a==i else 3-v for a,b,d,t,v in data["games"] if v is not None and i in (a,b)]
        require((sum(scored),sum(x>=2 for x in scored),len(scored))==(row[1],row[2],row[7]),"Team II seed standings disagree")
    require(len(data["own"])==data["table"][data["names"].index(TEAM)][7],"Missing own match results")

def main():
    s,m,data=read_page();check_seed(data)
    old=json.loads(m[1])
    if "--self-test" in sys.argv:
        print("Team II fixture and standings checks passed",flush=True);return
    require(NOW.date().isoformat()<"2027-07-01","Season ended: review source")
    soup=load(ROOT+"/saison/1106")
    matches,table=parse(soup,data["names"],allow_unscheduled=True)
    source_names=data["names"][:]
    prev={(a,b):v for a,b,d,t,v in data["games"]}
    require(set(prev)==set(matches),"Team II fixture identities changed")
    for k,(match,sets) in matches.items():
        require(prev[k] is None or match[4] is not None,"Team II source lost result")
        require(match[4] is None or not match[2] or match[2]<=NOW.date().isoformat(),"Future result")
    order=sorted(table,key=lambda i:table[i][0]); names=[data["names"][i] for i in order]; own=data["names"].index(TEAM)
    games=[]; played=[]
    for (h,v),(match,sets) in matches.items():
        games.append([order.index(h),order.index(v),*match[2:]])
        if match[4] is not None and own in (h,v):
            home=h==own;played.append([2026,match[2],"H" if home else "A",data["names"][v if home else h],sets if home else [s[::-1] for s in sets]])
    games.sort(key=lambda m:(m[2] or "9999",m[3],m[0],m[1]))
    played.sort(key=lambda m:(m[1],m[2],m[3]))
    newtable=[list(table[i]) for i in order]
    if names!=data["names"] or games!=sorted(data["games"],key=lambda m:(m[2] or "9999",m[3],m[0],m[1])) or played!=data["own"] or newtable!=data["table"]:
        data.update(names=names,games=games,table=newtable,own=played,stamp=NOW.strftime("%d.%m.%Y · %H:%M Uhr"))
    check_seed(data)
    print("Team II validated",len(games),"fixtures",len(names),"standings",len(played),"own matches",flush=True)
    print("Using locally stored historical archive.",flush=True)
    if data!=old and "--check" not in sys.argv:
        value=json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("<","\\u003c")
        s=s[:m.start(1)]+value+s[m.end(1):]
        s=re.sub(r"(Datenstand )\d{2}\.\d{2}\.\d{4}(?: · (?:\d{2}:\d{2} Uhr|Uhrzeit nicht erfasst))?",lambda m:m[1]+data["stamp"],s,count=1)
        PATH.write_text(s,encoding="utf-8")
    if "--save-snapshot" in sys.argv and "--check" not in sys.argv:
        from season_store import snapshot
        snapshot(PATH,matches,table,source_names)
if __name__=="__main__": main()
