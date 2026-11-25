"""Refresh SG Poing II independently; discover its pre-2025 SG Poing I archive."""
import json, re, sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from update_dashboard import parse, require

ROOT="https://www.ost.volleyball-freizeit.de"
PATH=Path("team2.html")
TEAM="SG Poing II"
NOW=datetime.now(ZoneInfo("Europe/Berlin"))
MARK=re.compile(r"const TEAM2_DATA=(.*?);\nconst teams=",re.S)

def load(url):
    with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html","Accept-Language":"de-DE,de;q=0.9","Cache-Control":"no-cache"}),timeout=15) as r:
        raw=r.read(4000001)
    require(len(raw)<=4000000,"HTML too large")
    return BeautifulSoup(raw,"html5lib")

def text(c): return " ".join(c.get_text(" ",strip=True).split())
def cells(row): return row.find_all(["td","th"],recursive=False)
def name_cell(c,names):
    candidates={text(c),*(text(x) for x in c.find_all(["a","span","strong"]))}
    found=candidates.intersection(names)
    return next(iter(found)) if len(found)==1 else None

def standing_cells(row):
    c=cells(row)
    if len(c)<7 or not re.fullmatch(r"\d+",text(c[0])): return None
    pairs=[]; nums=[]; name=None
    for x in c[1:]:
        s=text(x)
        m=re.search(r"(\d+)\s*:\s*(\d+)$",s)
        if m: pairs.append(tuple(map(int,m.groups())))
        elif re.fullmatch(r"\d+",s): nums.append(int(s))
        elif not name and s and re.search(r"[A-Za-zÄÖÜäöü]",s):
            a=x.find("a")
            name=text(a) if a and text(a) else s
    if not name or len(pairs)!=2 or len(nums) not in (2,3): return None
    return name,int(text(c[0])),nums[0],nums[1] if len(nums)==3 else None,*pairs[0],*pairs[1],nums[-1]

def season_data(url,year,exclude):
    sid=url.rsplit("/",1)[-1]
    if sid in exclude: return []
    soup=load(url)
    heading=" ".join(text(x) for x in soup.find_all(["h1","h2"]))
    require(re.search(rf"{year}\s*/\s*{year+1}",heading),"Wrong archive season heading")
    target=TEAM if year>=2025 else "SG Poing I"
    found=[]
    for tbl in soup.find_all("table"):
        standings=[s for row in tbl.find_all("tr") if (s:=standing_cells(row))]
        names=[s[0] for s in standings]
        if target not in names or sorted(s[1] for s in standings)!=list(range(1,len(standings)+1)): continue
        n,rank,p,w,sw,sl,bp,ba,g=next(s for s in standings if s[0]==target)
        record=dict(year=year,name=n,id=sid,rank=rank,n=len(names),p=p,w=w,sw=sw,sl=sl,bp=bp,ba=ba,g=g)
        matches=[]; seen=set()
        for row in soup.find_all("tr"):
            c=cells(row); tags=[name_cell(x,set(names)) for x in c]
            ix=[i for i,x in enumerate(tags) if x]
            if len(ix)!=2 or target not in [tags[i] for i in ix]: continue
            a,b=ix
            if tags[a]==tags[b]: continue
            prefix=" ".join(text(x) for x in c[:a])
            ds=re.findall(r"(?<!\d)(\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2}))(?!\d)",prefix)
            if not ds and "unbestimmt" not in prefix.lower(): continue
            d=datetime.strptime(ds[-1],"%d.%m.%Y" if len(ds[-1].split(".")[-1])==4 else "%d.%m.%y").date().isoformat() if ds else ""
            vals=[]
            for x in c[b+1:]:
                t=text(x)
                if re.fullmatch(r"\d+",t): vals.append(int(t))
                elif re.fullmatch(r"\d+\s*:\s*\d+",t): vals.extend(map(int,t.split(":")))
            if len(vals) not in (10,12): continue
            sets=[vals[i:i+2] for i in range(6,len(vals),2)]
            if any(a==b for a,b in sets) or vals[2:4]!=[sum(a>b for a,b in sets),sum(a<b for a,b in sets)] or vals[4:6]!=[sum(a for a,b in sets),sum(b for a,b in sets)]: continue
            home=tags[a]==target
            m=[year,d,"H" if home else "A",tags[b] if home else tags[a],sets if home else [s[::-1] for s in sets]]
            key=json.dumps(m)
            if key not in seen: matches.append(m);seen.add(key)
        ss=[s for m in matches for s in m[4]]
        totals=(len(matches),sum(a>b for a,b in ss),sum(a<b for a,b in ss),sum(a for a,b in ss),sum(b for a,b in ss))
        if totals!=(g,sw,sl,bp,ba):
            print("Archive detail incomplete",year,sid,totals,flush=True);matches=[]
        elif w is None:
            record["w"]=sum(sum(a>b for a,b in m[4])>len(m[4])/2 for m in matches)
        found.append((record,matches))
    return found

def scan_archive(data):
    first=Path("index.html").read_text(encoding="utf-8")
    # The original dashboard includes an uncertain 2015/16 historical name.
    # Exclude its existing season source to avoid double attribution.
    exclude=set(re.findall(r"/saison/(\d+)\"[^>]*>20\d\d/\d\d</a>",first))
    index=load(ROOT+"/saison/1095")
    years={}
    for a in index.find_all("a",href=True):
        m=re.fullmatch(r"(20\d\d)\s*/\s*20\d\d",text(a))
        if m and 2004<=int(m[1])<=2025:
            u=urljoin(ROOT,a["href"])
            if urlparse(u).netloc==urlparse(ROOT).netloc: years[int(m[1])]=u
    require(len(years)>=20,"Archive year navigation incomplete")
    archive={r["year"]:r for r in data["archive"]}
    hist=data["hist"][:]; failures=[]; unmatched=[]
    def scan_year(entry):
        y,u=entry
        if y==2025: return y,season_data(ROOT+"/saison/1095",y,exclude),[]
        soup=load(u)
        links=sorted({urljoin(ROOT,a["href"]) for a in soup.find_all("a",href=True) if re.search(r"/(?:saison|schedule/overview)/\d+$",urljoin(ROOT,a["href"])) and urlparse(urljoin(ROOT,a["href"])).netloc==urlparse(ROOT).netloc})
        links=sorted({ROOT+"/saison/"+l.rsplit("/",1)[-1] for l in links})
        require(0<len(links)<=30,"Unrecognized division links")
        found=[]; errors=[]
        for link in links:
            try: found.extend(season_data(link,y,exclude))
            except Exception as e: errors.append(link);print("Archive division unavailable",y,link,str(e),flush=True)
        return y,found,errors
    def safe_scan(entry):
        try: return scan_year(entry)
        except Exception as e: return entry[0],[],[str(e)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        for y,found,errors in pool.map(safe_scan,sorted(years.items(),reverse=True)):
            candidates={str(r["id"]):(r,m) for r,m in found}
            if errors: failures.append(y)
            if len(candidates)==1:
                r,m=next(iter(candidates.values()))
                archive[y]=r
                if m: hist=[x for x in hist if x[0]!=y]+m
                print("Archive verified",y,r["id"],r["g"],len(m),flush=True)
            elif len(candidates)>1:
                failures.append(y);print("Archive identity ambiguous",y,list(candidates),flush=True)
            else: unmatched.append(y)
    data["archive"]=sorted(archive.values(),key=lambda r:-r["year"])
    data["hist"]=sorted(hist,key=lambda m:(m[0],m[1],m[2],m[3]))
    data["archiveNote"]="Namenszuordnung laut Mannschaftsauskunft: bis 2024/25 SG Poing I, danach SG Poing II. "+str(len(archive))+" zugeordnete abgeschlossene Spielzeiten. Nicht auffindbare oder mehrdeutige Jahrgänge bleiben offen."
    if failures: data["archiveNote"]+=" Offene technische Prüfungen: "+", ".join(map(str,sorted(set(failures))))+"."
    if unmatched: data["archiveNote"]+=" Ohne eindeutigen Treffer: "+", ".join(map(str,sorted(unmatched)))+"."
    data["archiveScanned"]=len(years)>=22 and not failures

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
    if "--archive" in sys.argv and not data.get("archiveScanned"):
        try: scan_archive(data)
        except Exception as e: print("Archive scan deferred:",str(e),flush=True)
    if data!=old and "--check" not in sys.argv:
        value=json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("<","\\u003c")
        s=s[:m.start(1)]+value+s[m.end(1):]
        s=re.sub(r"(Datenstand )\d{2}\.\d{2}\.\d{4}(?: · (?:\d{2}:\d{2} Uhr|Uhrzeit nicht erfasst))?",lambda m:m[1]+data["stamp"],s,count=1)
        PATH.write_text(s,encoding="utf-8")
if __name__=="__main__": main()
