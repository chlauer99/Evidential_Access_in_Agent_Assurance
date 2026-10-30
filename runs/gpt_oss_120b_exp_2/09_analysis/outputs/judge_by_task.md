# GPT-OSS: Prüferleistung nach Task

Fehlererkennung = fail unter inhaltlichen Fehlern. Korrekte Zertifizierung = pass unter korrekten oder nur formatfehlerhaften Ergebnissen. wrong_order, pass_without_acting und no_finish ausgeschlossen wie in der Haupt-Prüferanalyse des Papers. Zahlen sind deskriptiv; kleine Nenner beachten.

## Fehlererkennung

| Task | Neutral | Spezifikation | Checkliste | Aktenzugriff |
|---|---:|---:|---:|---:|
| task1 | 1/107 (0.9 %) | 64/107 (59.8 %) | 2/107 (1.9 %) | 68/107 (63.6 %) |
| task2 | 0/4 (0.0 %) | 2/4 (50.0 %) | 0/4 (0.0 %) | 2/4 (50.0 %) |
| task3 | 1/1 (100.0 %) | 1/1 (100.0 %) | 1/1 (100.0 %) | 1/1 (100.0 %) |
| task4 | 10/24 (41.7 %) | 10/24 (41.7 %) | 23/24 (95.8 %) | 7/24 (29.2 %) |
| task5 | 6/15 (40.0 %) | 4/15 (26.7 %) | 10/15 (66.7 %) | 5/15 (33.3 %) |
| task6 | 26/59 (44.1 %) | 11/59 (18.6 %) | 43/59 (72.9 %) | 10/59 (16.9 %) |
| task7 | 12/57 (21.1 %) | 11/57 (19.3 %) | 37/57 (64.9 %) | 12/57 (21.1 %) |
| task8 | 0/2 (0.0 %) | 1/2 (50.0 %) | 0/2 (0.0 %) | 2/2 (100.0 %) |
| task9 | 29/116 (25.0 %) | 24/116 (20.7 %) | 28/116 (24.1 %) | 33/115 (28.7 %) |
| task10 | 14/22 (63.6 %) | 19/22 (86.4 %) | 14/22 (63.6 %) | 12/22 (54.5 %) |
| Gesamt | 99/407 (24.3 %) | 147/407 (36.1 %) | 158/407 (38.8 %) | 152/406 (37.4 %) |

### Veränderung gegenüber neutral auf gemeinsam gültigen Versuchen

| Task | Spezifikation | Checkliste | Aktenzugriff |
|---|---:|---:|---:|
| task1 | +58.9 PP | +0.9 PP | +62.6 PP |
| task2 | +50.0 PP | +0.0 PP | +50.0 PP |
| task3 | +0.0 PP | +0.0 PP | +0.0 PP |
| task4 | +0.0 PP | +54.2 PP | -12.5 PP |
| task5 | -13.3 PP | +26.7 PP | -6.7 PP |
| task6 | -25.4 PP | +28.8 PP | -27.1 PP |
| task7 | -1.8 PP | +43.9 PP | +0.0 PP |
| task8 | +50.0 PP | +0.0 PP | +100.0 PP |
| task9 | -4.3 PP | -0.9 PP | +4.3 PP |
| task10 | +22.7 PP | +0.0 PP | -9.1 PP |
| Gesamt | +11.8 PP | +14.5 PP | +13.3 PP |

## Korrekte Ergebnisse akzeptiert

| Task | Neutral | Spezifikation | Checkliste | Aktenzugriff |
|---|---:|---:|---:|---:|
| task1 | 8/13 (61.5 %) | 5/13 (38.5 %) | 10/13 (76.9 %) | 13/13 (100.0 %) |
| task2 | 52/116 (44.8 %) | 67/116 (57.8 %) | 105/116 (90.5 %) | 113/116 (97.4 %) |
| task3 | 13/119 (10.9 %) | 119/119 (100.0 %) | 111/119 (93.3 %) | 74/119 (62.2 %) |
| task4 | 62/96 (64.6 %) | 68/96 (70.8 %) | 65/96 (67.7 %) | 92/96 (95.8 %) |
| task5 | 80/80 (100.0 %) | 80/80 (100.0 %) | 75/80 (93.8 %) | 79/80 (98.8 %) |
| task6 | 42/61 (68.9 %) | 49/61 (80.3 %) | 53/61 (86.9 %) | 61/61 (100.0 %) |
| task7 | 63/63 (100.0 %) | 63/63 (100.0 %) | 58/63 (92.1 %) | 63/63 (100.0 %) |
| task8 | 110/110 (100.0 %) | 110/110 (100.0 %) | 110/110 (100.0 %) | 18/109 (16.5 %) |
| task9 | — | — | — | — |
| task10 | 61/63 (96.8 %) | 60/63 (95.2 %) | 62/63 (98.4 %) | 62/63 (98.4 %) |
| Gesamt | 491/721 (68.1 %) | 621/721 (86.1 %) | 649/721 (90.0 %) | 575/720 (79.9 %) |

### Veränderung gegenüber neutral auf gemeinsam gültigen Versuchen

| Task | Spezifikation | Checkliste | Aktenzugriff |
|---|---:|---:|---:|
| task1 | -23.1 PP | +15.4 PP | +38.5 PP |
| task2 | +12.9 PP | +45.7 PP | +52.6 PP |
| task3 | +89.1 PP | +82.4 PP | +51.3 PP |
| task4 | +6.2 PP | +3.1 PP | +31.2 PP |
| task5 | +0.0 PP | -6.2 PP | -1.2 PP |
| task6 | +11.5 PP | +18.0 PP | +31.1 PP |
| task7 | +0.0 PP | -7.9 PP | +0.0 PP |
| task8 | +0.0 PP | +0.0 PP | -83.5 PP |
| task9 | — | — | — |
| task10 | -1.6 PP | +1.6 PP | +1.6 PP |
| Gesamt | +18.0 PP | +21.9 PP | +11.8 PP |
