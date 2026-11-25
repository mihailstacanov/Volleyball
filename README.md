# SG Poing Volleyball Dashboard

[![Dashboard](https://github.com/mihailstacanov/Volleyball/actions/workflows/volleyball.yml/badge.svg)](https://github.com/mihailstacanov/Volleyball/actions/workflows/volleyball.yml)
[![Release](https://img.shields.io/github/v/release/mihailstacanov/Volleyball)](https://github.com/mihailstacanov/Volleyball/releases)

Ein mobilfreundliches Statistik- und Analyse-Dashboard für die beiden Mixed-Volleyballmannschaften der SG Poing in Oberbayern Ost. Spielpläne, Ergebnisse, Tabellen, historische Daten und interaktive Auswertungen an einem Ort.

## Dashboard öffnen

| Mannschaft | Liga 2026/27 | Dashboard | Offizielle Ligadaten |
| --- | --- | --- | --- |
| SG Poing I | 2. Süd | [Öffnen](https://mihailstacanov.github.io/Volleyball/) | [Ligaverband](https://www.ost.volleyball-freizeit.de/saison/1096) |
| SG Poing II | 3. Mitte | [Öffnen](https://mihailstacanov.github.io/Volleyball/team2.html) | [Ligaverband](https://www.ost.volleyball-freizeit.de/saison/1106) |

Die Website kann auf unterstützten Mobilgeräten zum Startbildschirm hinzugefügt werden. Sie ist öffentlich zugänglich und benötigt kein Benutzerkonto. Eine garantierte Offline-Funktion gibt es nicht.

## Funktionen

- **Übersicht:** Tabellenplatz, Siege, Punkte, Satzbilanz, letzte Ergebnisse, nächste Spiele und Auf-/Abstiegszonen.
- **Saisonanalyse:** Heim- und Auswärtsbilanz, Form, Satz- und Ballpunktstatistik.
- **Prognose:** Elo-Modell, Monte-Carlo-Simulation, Restprogramm und Wahrscheinlichkeiten für die Ligazonen; eigene Spielergebnisse können für Szenarien vorgegeben werden.
- **Spielplan & Hallen:** Spielkalender, Hallenkarte, ICS-Kalenderdatei und Gegneranalyse mit Direktduellen.
- **Historie:** Saisonarchiv, Rekorde, historische Einzelspiele und Direktvergleiche.
- **Season Wrapped:** sechs Kapitel zum ausgewählten Saisonrückblick.
- **Visual Analytics:** zehn interaktive Diagramme.

### Visual Analytics

| Visualisierung | Inhalt |
| --- | --- |
| Liga Race | Tabellenentwicklung |
| Liga Heatmap | Ergebnismatrix |
| Power Ranking Race | Elo-Entwicklung |
| Team DNA | Vergleich zweier frei wählbarer Spielzeiten |
| Season Momentum | Formverlauf |
| Historical Race | Kumulierte Siege |
| Satzverlauf | Satzendstände einzelner Spiele |
| Opponent DNA | Profil eines frei wählbaren aktuellen Ligagegners |
| Season Journey | Spielchronik |
| Aufstiegsrennen | Modellwahrscheinlichkeiten im Saisonverlauf |

Prognosen sind statistische Schätzungen, keine offiziellen Vorhersagen. Fehlende historische Detaildaten werden nicht erfunden. Rekonstruierte Tabellen können bei Gleichständen von der offiziellen Rangfolge abweichen.

## Daten und Aktualisierung

Datenquelle ist das öffentliche Portal [Volleyball-Freizeit Oberbayern Ost](https://www.ost.volleyball-freizeit.de/). Die Skripte laden nur die beiden aktuellen Ligen. Historische Ergebnisse werden aus dem lokalen JSON-Archiv übernommen.

1. Aktuelle Spielpläne und Tabellen abrufen.
2. Vollständigkeit, Begegnungsidentitäten und Konsistenz der offiziellen Werte prüfen.
3. Daten mit dem gespeicherten Archiv zusammenführen und saisonbezogene Snapshots speichern.
4. Geprüfte HTML-Dateien und Snapshots in Git übernehmen und die Website über GitHub Pages veröffentlichen.

**Datenstand** bezeichnet die letzte erfolgreiche Live-Prüfung in der Zeitzone Europe/Berlin, auch wenn sich keine Spielergebnisse geändert haben. Fehlerhafte Abrufe erhalten keinen neuen erfolgreichen Prüfzeitpunkt.

Der manuelle Datenabruf ist dem Repository-Eigentümer vorbehalten: [Actions → Volleyball Dashboard → Run workflow](https://github.com/mihailstacanov/Volleyball/actions/workflows/volleyball.yml), Branch `main`. Normale Pushes auf main führen lokale Prüfungen und eine Veröffentlichung aus, ohne historische Ligaseiten erneut abzurufen.

## Projektstruktur

```text
index.html                     SG Poing I
team2.html                     SG Poing II
manifest.webmanifest           App-Manifest
data/
  history/                     Dauerhaft gespeicherte Historie
  seasons/2026-27/              Aktuelle Saison-Snapshots
  README.md                    Datenformat und Saisonwechsel
scripts/
  update_dashboard.py           Aktualisierung SG Poing I
  update_team2.py               Aktualisierung SG Poing II
  season_store.py               Lokales Archiv und Snapshots
.github/
  workflows/                   Prüfung, Aktualisierung und Releases
  dependabot.yml                Abhängigkeitsaktualisierungen
requirements.txt               Python-Abhängigkeiten
SECURITY.md                    Sicherheitshinweise
CHANGELOG.md                   Versionshistorie
VERSION                        Release-Version
```

Beim Saisonwechsel bleiben die alten Snapshots erhalten. Die vorbereiteten Archivdateien werden aus den gespeicherten vollständigen Saisonergebnissen erzeugt. Neue Liga-IDs, Mannschaften, Hallen, Ligazonen und Saisonbezüge müssen vor der Umstellung geprüft werden. Details: [Datenarchiv](data/README.md).

## Lokale Entwicklung

Voraussetzungen: Python 3.10+ und die in requirements.txt festgelegten Pakete.

```bash
python -m pip install -r requirements.txt
python scripts/update_dashboard.py --self-test
python scripts/update_team2.py --self-test
python scripts/season_store.py verify
python -m http.server 8000
```

Dashboard im Browser: http://localhost:8000/

Die Selbsttests verwenden lokale bzw. synthetische Daten und ändern keine produktiven Ergebnisse. Ein Live-Datenabruf ist dafür nicht erforderlich.

## Sicherheit und Releases

Dependabot prüft Python-Pakete und GitHub Actions wöchentlich. Pull Requests werden vor einer Übernahme geprüft; die Veröffentlichung verwendet GitHub Actions mit minimalen Job-Berechtigungen. Zugangsdaten gehören nicht in öffentlich ausgelieferte Dateien. Siehe [Security Policy](SECURITY.md).

Versionsänderungen in VERSION auf main lösen die Release-Pipeline aus. Nach erfolgreichen lokalen Tests wird ein GitHub Release mit dem passenden Git-Tag und den Versionshinweisen erstellt. Die laufende Aktualisierung der Ligadaten benötigt keine neue Softwareversion.

[GitHub Releases](https://github.com/mihailstacanov/Volleyball/releases) · [Changelog](CHANGELOG.md)

## Hinweise

Dieses Dashboard ist eine eigenständige Auswertung öffentlich verfügbarer Ligadaten. Maßgeblich bleiben die offiziellen Veröffentlichungen des Ligaverbands. Es werden keine Spielerprofile oder privaten Mannschaftschats verarbeitet. Historische Namenswechsel und Datenlücken sind in den Archivdaten gekennzeichnet.
