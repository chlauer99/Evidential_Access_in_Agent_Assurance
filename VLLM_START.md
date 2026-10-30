> Aktueller Umfang: Enthalten sind nur die Paper-Konfigurationen aus [harness/configs/README.md](harness/configs/README.md). Die unten historisch beschriebenen Smoke-Tests und Qwen-Vorläufer sind nicht mehr enthalten; für Qwen gilt `harness/configs/qwen3_8_27b_exp_3.yaml`.

# Experiment mit GPT-OSS auf dem vLLM-Server

Die vorhandene OpenAI-kompatible Schnittstelle wird für **alle Modellaufrufe** genutzt:
Agenten, normale Prüfer, Prüfer mit Aktenzugriff, Wissensfragen und Verifikationshinweis.
Es werden keine Aufrufe an OpenAI oder OpenRouter konfiguriert.

## Modell und Versuchsdesign

- API-Basis: `http://192.168.92.194:10121/v1` (vLLM verwendet hier den `/v1`-Pfad).
- Modell-ID: `openai/gpt-oss-120b`.
  `check_endpoint.py` prüft, ob diese ID vom Server angeboten wird.
  Die Server-ID allein garantiert nicht die geladenen Gewichte.
- Konfiguration: `harness/configs/gpt_oss_120b_exp_2.yaml`.
- Ohne Authentifizierung wird `EMPTY` gesendet. Falls der Server einen Schlüssel verlangt:
  `LOCAL_LLM_API_KEY` in der Umgebung setzen; nicht in die YAML schreiben.

Die Konfiguration führt **einen Hauptlauf ohne Pilotgruppen** aus:
300 Aufgaben × 4 Versuche = **1.200 Agentenversuche**. Es gibt einen Modell-Eintrag
und einen Prüfer. GPT-OSS 120B bewertet die abgeschlossenen Hauptlauf-Versuche unter
allen vier Bedingungen: Ablaufprotokoll, Schnittstellendokumentation, Checkliste und
eigener Aktenzugriff (bis zu vier GET-Abfragen). Aktenzugriff wird für alle abgeschlossenen
Hauptlauf-Versuche vorgesehen, nicht nur für eine nach Fehlertyp ausgewählte Stichprobe.

Zwei nicht-LLM-basierte Kontrollen (Referenzwiedergabe und Nichtstun) laufen je einmal
über alle 300 Aufgaben. Sie werden unter den ersten drei Prüfbedingungen beurteilt.
Wissensfragen und Wiederholungen mit Verifikationshinweis bleiben erhalten; die Auswahl
für diese Wiederholungen erfolgt ausschließlich aus dem neuen Hauptlauf. Gibt es keine
Fehler der Informationsbeschaffung, wird das Hinweisexperiment als nicht anwendbar übersprungen.

Die internen Dateinamen `full_deepseekv32` und `cue_deepseekv32` bleiben für die vorhandenen
Hilfsskripte erhalten. Sie bezeichnen hier GPT-OSS-Aufrufe. Pilotdateien werden weder erzeugt
noch für die Auswertung benötigt. Der neue Laufname `gpt_oss_120b_exp_2` trennt diesen
Versuch von den bisherigen Ergebnissen; alte Laufdateien bleiben erhalten.

Die Auswertung verwendet `harness/pipeline/analyse_single.py` statt der historischen
Drei-Modell-Auswertung. Sie berechnet Fehlerverteilungen, Erkennungsraten, korrekte
Akzeptanz, Fehlalarme, Youden-J und gepaarte Unterschiede zwischen Prüfbedingungen
mit 95%-Intervallen durch Resampling ganzer Aufgaben (1.000 Ziehungen, Seed 2027).
Fehlende/ungültige Urteile werden explizit ausgewiesen; gepaarte Vergleiche verwenden nur
Versuche mit gültigem Urteil in beiden Bedingungen. Als Fehler zählen wie in der ursprünglichen zentralen Prüferauswertung
`substantive_answer_error`, `omission` und `commission`.
Intern als `wrong_order` gespeicherte Fälle erscheinen als `unclassified`;
sie gehen weder in Prüferkennzahlen noch in Fehlermechanismus- und Provenienzverteilungen ein.
Auch `pass_without_acting` und `no_finish` bleiben aus den Prüferkennzahlen ausgeschlossen.
Die internen Rohklassifikationen bleiben für spätere Nachprüfungen erhalten.

Die Modelleinstellungen unterscheiden sich ebenfalls vom Paper. Es gibt keine Aussagen
über Modell-/Entwicklerunterschiede oder unabhängige Prüfer. Schritt 10 vergleicht nur
Hauptlauf-Ergebnisraten beschreibend mit dem archivierten DeepSeek-Hauptlauf. Die
historischen Paper-Tabellen und -Abbildungen werden in diesem Modus nicht erzeugt.

## Vorbereitung

Alle folgenden Befehle im Hauptverzeichnis des Repositories ausführen.
Python 3.11 oder neuer und Docker mit laufendem Docker-Dienst werden benötigt.
Der FHIR-Testserver läuft lokal auf Port 8080; der vLLM-Server bleibt auf dem angegebenen
Netzwerkrechner. Netzwerk/VPN-Zugriff auf diesen Rechner muss vorhanden sein.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'openai>=1.40' requests pandas numpy matplotlib pyyaml tqdm
export NO_PROXY="${NO_PROXY:+$NO_PROXY,}192.168.92.194,localhost,127.0.0.1"
export no_proxy="$NO_PROXY"
```

Alternativ kann die vorhandene Conda-Umgebung aus `environment-harness.yml` verwendet werden.

## 1. Endpunkt und Antwortformate prüfen

```bash
python harness/scripts/check_endpoint.py --config harness/configs/gpt_oss_120b_exp_2.yaml
```

Der Test fragt `/v1/models` ab und sendet zwei kleine Testprompts für Agentenaktion und
Prüfer-JSON. Er benötigt keine Patientenakten und startet kein Experiment. Bei falscher
Modell-ID, leerer/abgeschnittener Antwort oder falschem Format endet er mit Fehlerstatus.
Bei Verbindungsfehlern zuerst Netzwerk/VPN, Port und laufenden vLLM-Dienst prüfen.

GPT-OSS erzeugt Reasoning zusätzlich zur finalen Antwort. Der Server muss diese korrekt
trennen; das Harness verwendet `message.content`, nicht das separate Reasoning-Feld.
Konfiguriert sind `reasoning_effort: low` und 8.192 Ausgabetokens auch für Prüfer und Probes,
damit deren ursprüngliche 200-/400-Token-Grenzen nicht das Reasoning abschneiden.
Das sind dokumentationspflichtige Abweichungen vom Paper-Protokoll.
Der strikte Aktionsparser bleibt aktiv. `strip_reasoning` entfernt gegebenenfalls
`<think>`-Blöcke, ist aber kein Parser für beliebige rohe Harmony-Ausgaben.

Der Server braucht genügend Kontext für Aufgabenbeschreibung, wachsenden Verlauf und
Ausgabebudget; 32.768 Tokens sind ein sinnvoller Startwert, lange Akten können mehr brauchen.
Der kurze Endpunkttest prüft diese Kapazität nicht. Hinweise zum Serverformat:
https://docs.vllm.ai/en/stable/features/reasoning_outputs/

## 2. Optional: technischer Funktionstest

```bash
python harness/run_pipeline.py --config harness/configs/vllm_gpt_oss_smoke.yaml --steps 0-1 --yes
```

Dieser optionale technische Test startet den FHIR-Server und bearbeitet drei Beispielaufgaben
mit je einem Versuch. Er ist kein wissenschaftlicher Pilot und wird nicht in die Hauptauswertung
übernommen. Ergebnisse stehen separat unter `runs/vllm_gpt_oss_main_v2_smoke/`.
Die Smoke-Konfiguration nur mit Schritten 0–1 verwenden; die vollständigen Auswertungen
setzen das volle Versuchsdesign voraus.
Vor dem großen Lauf `01_agents/`-Logs und `mab_runs/*/results.jsonl` prüfen:
keine API-/Kontextfehler, keine systematisch leeren Antworten und keine systematischen
`AGENT_INVALID_ACTION`-Abbrüche. Inhaltlich falsche Antworten sind erwartete Messdaten.

## 3. Vollständigen Ablauf starten

```bash
python harness/run_pipeline.py --config harness/configs/gpt_oss_120b_exp_2.yaml --dry-run
python harness/run_pipeline.py --config harness/configs/gpt_oss_120b_exp_2.yaml --yes
```

Die Schritte 0–10 umfassen Serverstart, Agenten, Kontrollen, regelbasierte Prüfung,
Fehlerzuordnung, Provenienz, KI-Prüfer, Wissensfragen, Hinweisexperiment und Auswertung.
`--yes` erlaubt die Modellaufrufe auch bei lokalen Endpunkten. Die angezeigten Kosten
sind mit 0 konfiguriert und berücksichtigen keine eigenen Hardware-/Stromkosten;
Laufzeitschätzungen stammen aus der Originalstudie, nicht von diesem vLLM-Server.
Die Konfiguration verwendet zunächst nur einen Worker pro Modellprozess.

Ergebnisse:

- `runs/gpt_oss_120b_exp_2/mab_runs/`: neue Abläufe und Prüferurteile.
- `runs/gpt_oss_120b_exp_2/derived/`: Fehlerzuordnungen.
- `runs/gpt_oss_120b_exp_2/09_analysis/outputs/`: CSV-Auswertungen, `summary.json` und `report.md`.
- `runs/gpt_oss_120b_exp_2/10_compare/`: Vergleich mit archivierten Paper-Zahlen.

Der gleiche Startbefehl setzt einen unterbrochenen Lauf anhand der vorhandenen Dateien
und Schrittmarker fort. Vor einem neuen Modell oder veränderten Einstellungen einen
neuen `name:` verwenden, damit Ergebnisse nicht vermischt werden. Nach Rechner-/Docker-
Neustart den FHIR-Server wieder starten; ein vorhandener Schrittmarker startet ihn beim
Fortsetzen nicht erneut (z. B. `docker start medagentbench-fhir`, sofern er noch existiert,
sonst der Docker-Startbefehl aus dem Dry Run).

## Fortschritt während eines laufenden Experiments

In einem zweiten Terminal im Paketordner starten (keine zusätzlichen Pakete nötig):

```bash
python3 harness/scripts/monitor_progress.py
```

Die Anzeige aktualisiert sich alle fünf Sekunden und zeigt gespeicherte Agentenversuche,
Protokollabbrüche, offene API-Fehler, offizielle Bestehenszahlen, Kontrollversuche,
Prüferurteile je Bedingung, Wissensfragen, Hinweisexperiment und das zuletzt beschriebene
Log. Prozentwerte beziehen sich auf die jeweilige Versuchsgruppe, nicht auf die gesamte
Laufzeit des Experiments. Ein Fehler bei der Aufgabenlösung ist ein Messergebnis, kein
technischer Abbruch. Schrittmarker und Logalter allein beweisen keine Prozessaktivität.

Sobald alle Schritte 0–10 gültige Abschlussmarker haben, zeigt der Monitor den letzten
Status einschließlich offener Probleme und beendet sich automatisch. Ungültige Urteile
verhindern das Ende nicht und werden nicht automatisch wiederholt.
`Strg+C` beendet nur den Monitor. Der bereits laufende Versuch wird nicht verändert.
Für einen einzelnen Statusbericht `--once` ergänzen; für den technischen Funktionstest
`--config harness/configs/vllm_gpt_oss_smoke.yaml --steps 0-1` verwenden.
Für andere Teilläufe mit `--steps` dieselben erwarteten Schritte wie bei der Pipeline angeben.
Ein bereits laufender Monitor muss einmal beendet und neu gestartet werden, um die Änderung zu übernehmen.

Neu gestartete Pipeline-Prozesse zeigen außerdem die Unterprozess-Logs direkt im Terminal
und alle 30 Sekunden eine Prozessmeldung. Bereits laufende Pipeline-Prozesse übernehmen
diese Änderung erst beim nächsten Start; der separate Monitor funktioniert sofort.

## Validierungsstand

Die neue Hauptlauf-Konfiguration und der unveränderte Paper-Modus wurden per Dry Run geprüft.
Offline-Tests prüfen außerdem die Auswertung ohne Pilotdateien, gepaarte Nenner, fehlende/ungültige
Urteile, leere Teilmengen und das Überspringen eines Hinweisexperiments ohne geeignete Aufgaben. Der echte Serverzugriff und ein
kompletter Modell-/FHIR-Durchlauf wurden nicht erfolgreich ausgeführt. Die übernommenen Regeln zur Fehler- und Provenienzkodierung sind weiterhin auf den Benchmark
zugeschnitten. Endpunkttest und optionaler Funktionstest helfen, die lokale Installation vor
dem vollständigen Lauf zu prüfen.

## Verbindliche Prüferformate

Die vLLM-Konfiguration aktiviert `structured_output: true` für alle vier
Prüfbedingungen. Jede Anfrage übergibt ein verbindliches JSON-Schema.
Urteile enthalten genau `verdict`, `confidence` (Ganzzahl 0–100),
`issue_type`, `issues` (höchstens drei Texte) und `rationale`.
Der Aktenprüfer verwendet `{"action":{"query":"<url>"}}` für Abfragen und
`{"action":{...Urteil...}}` für das abschließende Urteil. Nach Ausschöpfen
der Abfragen erlaubt das Schema nur noch ein Urteil.

Der Endpunkt muss JSON-Schema-Ausgaben unterstützen. Der Vorbereitungstest
prüft Urteil, Abfrage und abschließendes Aktenurteil. Es gibt keinen
automatischen Rückfall auf freie Textausgabe. Ungültige oder abgeschnittene
Antworten werden protokolliert und lassen den Prüfschritt fehlschlagen;
er erhält keine erfolgreiche Abschlussmarkierung. Rohantworten,
Abschlussgründe und bei Aktenabfragen HTTP-Status und Antworttext werden gespeichert.

Die ursprünglichen Aktionsformate der ausführenden Agenten und die Wissensfragen
bleiben unverändert. Das Schema sichert die Form der Prüferausgabe,
nicht die inhaltliche Richtigkeit des Urteils.

## Fortschrittsanzeige

Agentenläufe, Kontrollen, jede Prüfbedingung, Wissensfragen und Wiederholungen mit
Verifikationshinweis zeigen automatisch einen tqdm-Balken mit Anzahl, Prozent,
Laufzeit und geschätzter Restzeit. Vor jedem Lauf steht der Experimentname.
Bei Wiederaufnahme zählt der Balken die noch ausstehenden Einheiten; bereits
gespeicherte Ergebnisse werden übersprungen. Ein Balkenschritt entspricht einem
abgearbeiteten Versuch bzw. einer Wissensfrage, nicht einem einzelnen Token.
Fehlgeschlagene Aufrufe zählen als abgearbeitet; Fehlermeldungen und der Abschlussstatus
zeigen, ob der Lauf erfolgreich war. Während einer langen Modellantwort kann
der Balken stehen bleiben. Die Prozessmeldung erscheint weiterhin alle 30 Sekunden.

Falls nötig, einmal in der aktiven Umgebung installieren: `python -m pip install tqdm`.

## Wiederholungen bei Fehlern des Modellservers

Die Aktenprüfung wiederholt vorübergehende API-Fehler (Verbindung/Timeout,
HTTP 408/409/429 und 5xx) bis zu dreimal mit 2, 4 und 8 Sekunden Pause.
Die zuvor verwendeten zehn unsichtbaren SDK-Wiederholungen sind dafür deaktiviert.
Jede Wiederholung verwendet dieselben Nachrichten, Modellparameter und dasselbe Schema.
Erfolgreiche Antworten werden nicht wegen ihres Inhalts erneut angefordert.

Jeder Fehlversuch wird unter
`mab_runs/<run>/judge_<tag>_request_errors.jsonl` gespeichert:
Aufgabe, Versuch, Gesprächsrunde, Zeit, HTTP-Status, Fehlermeldung,
Wiederholungsnummer und ein Fingerabdruck der Anfrage. Nach ausgeschöpften
Wiederholungen wird ein fehlendes Urteil samt bisheriger Gesprächsrunden gespeichert;
bei deaktiviertem continue_on_errors bleibt der Prüfschritt fehlgeschlagen. Beim erneuten Start werden gültige Urteile übersprungen.
Die Anzahl zusätzlicher Versuche lässt sich beim direkten Aufruf von
`judge_agentic.py` über `--request-retries` ändern (Standard: 3).

## Mit fehlenden Aktenurteilen fortfahren

Die vLLM-Konfiguration setzt `record_access.continue_on_errors: true`.
Nach ausgeschöpften API-Wiederholungen oder ungültigen Ausgaben werden fehlende
Urteile gespeichert; die Pipeline fährt mit Wissensfragen, Verifikationshinweis und
Auswertung fort. Fehlende/ungültige Urteile gehen nicht in die Prüferkennzahlen ein.
Unerwartete Programm- oder Dateifehler stoppen weiterhin den Lauf.

`06_judges/gpt-oss-120b_access_status.json` enthält den Abschlussstatus und die
Anzahl fehlender neuer Urteile. Auch `06_judges/DONE.json` kennzeichnet den
Abschluss mit fehlenden Urteilen. Der Schritt wird bei normaler Wiederaufnahme
übersprungen. Um fehlende Urteile später nachzuholen, nur diese DONE.json entfernen
und Schritt 6 erneut starten; danach die Auswertung in Schritten 9–10 erneuern.
Bereits gültige Urteile werden dabei übersprungen.

## Weiterer Hauptlauf mit Qwen3.8 27B

Konfiguration: `harness/configs/vllm_qwen3_8_27b.yaml`.
Endpunkt: `http://192.168.92.194:10122/v1`, Modell-ID: `Qwen/Qwen3.8-27B`.
Ergebnisordner: `runs/qwen3_8_27b_exp_1/`.

Der Lauf verwendet Qwen für sämtliche Modellaufrufe. Versuchsanzahl, Prüfbedingungen,
JSON-Schemata, Wiederholungen und Fortsetzen bei fehlenden Aktenurteilen entsprechen
der GPT-OSS-Konfiguration. Es gibt keine Pilotversuche. Die Kontextlänge muss auf
dem Modellserver mindestens 240.000 Tokens betragen; der Vorbereitungstest prüft
die Serverangabe. Das Ausgabelimit bleibt 8.192 Tokens und liegt innerhalb dieses
Kontextfensters. Die GPT-OSS-spezifische Einstellung `reasoning_effort: low` wird
nicht übertragen; Qwen verwendet die Reasoning-Voreinstellung seines Servers.
Damit ist die Reasoning-Einstellung zwischen den Modellen nicht kontrolliert gleich.

Im Paketordner ausführen:
```bash
./.venv/bin/python harness/scripts/check_endpoint.py --config harness/configs/vllm_qwen3_8_27b.yaml
./.venv/bin/python harness/run_pipeline.py --config harness/configs/vllm_qwen3_8_27b.yaml --yes
```

Die internen Rollen `full_deepseekv32` und `cue_deepseekv32` bleiben aus
Kompatibilitätsgründen erhalten; sie rufen ausschließlich das konfigurierte Qwen-Modell auf.
