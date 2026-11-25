# Ligadaten und Saisonarchiv

Die Historie liegt dauerhaft in Git:

- `history/team1.json`: historische Saisonzeilen und Einzelspiele der heutigen SG Poing I.
- `history/team2.json`: historische Saisonstatistik und Einzelspiele der heutigen SG Poing II.
- `seasons/2026-27/team1.json` und `team2.json`: aktuelle Saison-Snapshots. Enthalten alle bekannten Ligapaarungen, die eigenen Satzstände und nach dem nächsten erfolgreichen manuellen Update auch die vollständigen Satzstände und Tabellenwerte aller Ligateams.

Die historischen JSON-Dateien sind die Datenquelle. Vor der Aktualisierung werden deren Inhalte wieder in die HTML-Dateien eingebettet. Dadurch bleiben alle bisherigen Auswertungen verwendbar. Fehlende Jahrgänge, unvollständige Daten und unsichere Namenszuordnungen bleiben gekennzeichnet.

Der normale Workflow lädt nur die beiden aktuellen Staffeln. Push-Prüfungen benutzen lokale Daten und synthetische Tests. Es gibt keinen automatischen Archiv-Crawler mehr.

## Saisonwechsel

Die Snapshots der abgelaufenen Saison bleiben dauerhaft unter ihrem Jahrgang erhalten. Sie werden nicht gelöscht oder mit neuen Saisonwerten überschrieben. Nach Abschluss der Saison erzeugt `python scripts/season_store.py prepare-rollover --year 2026` aus beiden vollständig gespeicherten Snapshots die vorbereiteten historischen JSON-Dateien für die nächste Saison unter `data/rollover/2027-28/`. Die aktive Historie bleibt unverändert, bis die neuen Saison-Templates eingerichtet und die vorbereiteten Dateien übernommen werden. Der Befehl benötigt kein Netzwerk und verweigert unvollständige Snapshots. Ein Snapshot mit `complete: false` ist kein vollständig abgeschlossenes Ligaergebnis.

Für eine neue Saison müssen die beiden aktuellen Liga-IDs, Mannschaften, Hallen, Auf-/Abstiegszonen und Saisonbezüge der HTML-Templates geprüft und angepasst werden. Die bestehenden Aktualisierungsskripte verweigern bewusst einen Lauf nach dem 30.06.2027, bis die Umstellung erfolgt ist. Kein automatisches Raten von Liga-IDs, kein erneutes Laden früherer Spielzeiten.

Namenswechsel: bis 2024/25 heutige SG Poing I unter SG Poing II, heutige SG Poing II unter SG Poing I; ab 2025/26 umgekehrt. Unsichere ältere Zuordnungen sind aus den bisherigen Daten übernommen.
