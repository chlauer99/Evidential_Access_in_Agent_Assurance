# Fehlende Cross-Judge-Bedingungen ergänzen

Aus `ecis2027_epidemische_Fehler/` in der bestehenden Harness-Umgebung:

```sh
python harness/scripts/backfill_cross_judge.py
python harness/scripts/backfill_cross_judge.py --execute
```

Der erste Befehl prüft die vorhandenen Eingaben und zeigt nur den Plan.
Der zweite ergänzt API Specification (`_spec`), Checklist (`_verify`) und
Record Access (`_access`) für beide bestehenden Kombinationen:

- GPT-OSS Run A (`gpt_oss_120b_exp_2`) mit Qwen als Judge.
- Qwen (`qwen3_8_27b_exp_3`) mit GPT-OSS als Judge.

Ergebnisse werden unter `runs/cross_judge_exp_1/on_gpt_oss_attempts/mab_runs/full_deepseekv32/`
bzw. `on_qwen_attempts/mab_runs/full_deepseekv32/` ergänzt. Die Neutral-Bewertungen
bleiben bestehen. Gültige Bewertungen mit der aktuellen strukturierten Output-Schema-Version
werden von den Judge-Programmen übersprungen; fehlende, ungültige oder ältere Schema-Ausgaben
werden erneut bewertet. Nach Unterbrechung denselben Befehl erneut starten.

Fehlende Kopien von `results.jsonl` und `answers/` werden aus den Ursprungsläufen
übernommen. Vorhandene Eingaben müssen mit dem Ursprung übereinstimmen.
Die Record-Access-Auswahl wird direkt aus dem jeweiligen Ursprungslauf gelesen;
es erfolgt keine neue Stichprobenziehung. Agenten, Controls, Grading, Probes und
Cue-Läufe werden nicht gestartet. Der separate GPT-OSS Run B wird nicht verwendet.

Voraussetzungen: bestehende Harness-Umgebung mit allen Abhängigkeiten, erreichbare
Modell-Endpunkte und für Record Access derselbe Benchmark-FHIR-Server mit dem
ursprünglichen Datenbestand unter `http://localhost:8080/fhir/`.
Das Skript startet oder verändert den Server nicht. Bei einem Fehler stoppt es;
Record-Access-Statusdateien stehen im jeweiligen `on_*_attempts`-Ordner.

Optional nur eine Kombination oder einzelne Bedingungen ausführen:

```sh
python harness/scripts/backfill_cross_judge.py --pair on_gpt_oss_attempts --conditions spec checklist --execute
python harness/scripts/backfill_cross_judge.py --pair on_qwen_attempts --conditions access --execute
```

Andere Speicherorte/Endpunkte: `--runs-root /pfad/zu/runs`, `--qwen-url URL`,
`--gpt-oss-url URL`. Die bestehenden Vergleichs-/Paper-Auswertungsskripte betrachten
diese beiden Cross-Judge-Kombinationen bislang nur unter Neutral; das Nachholen
allein erweitert deren Tabellen noch nicht automatisch.
