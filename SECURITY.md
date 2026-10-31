# Sicherheitsrichtlinie

🇬🇧 **[English Version](#english-version)** below

## Unterstützte Versionen

| Version | Sicherheitsupdates |
|---|---|
| 4.0.x | ✅ |
| < 4.0 | ❌ |

## Sicherheitslücke melden

Bitte melde Sicherheitslücken **nicht** als öffentliches Issue.

Nutze stattdessen die private Meldung von GitHub: im Repository unter **Security → Report a vulnerability**. Hilfreich sind:

- betroffene Version oder Commit
- Beschreibung und Auswirkung
- Schritte zum Nachvollziehen, idealerweise mit Beispiel-Request
- falls vorhanden: ein Vorschlag zur Behebung

Du bekommst innerhalb von 7 Tagen eine erste Rückmeldung. Das Projekt wird in der Freizeit gepflegt, eine Behebung kann daher etwas dauern. Nach der Behebung wird die Lücke im [CHANGELOG](CHANGELOG.md) und als GitHub Security Advisory veröffentlicht. Auf Wunsch wirst du dort genannt.

## Geltungsbereich

Relevant sind vor allem:

- Umgehen der API-Key-Prüfung oder von `TRUSTED_IPS`
- Zugriff auf Dateien ausserhalb von `recordings/`
- Einschleusen von Befehlen oder Argumenten in SDR- und Decoder-Prozesse
- XSS oder Formel-Injection durch empfangene Funkdaten (APRS, POCSAG, AIS, Transkripte)
- Geheimnisse, die in Images, Logs oder Exporten landen

Nicht als Sicherheitslücke gelten Installationen, die gegen die Hinweise in [docs/security.md](docs/security.md) betrieben werden, zum Beispiel mit `ALLOW_INSECURE=true` oder ohne Reverse-Proxy im Internet.

---

## English Version

### Supported versions

| Version | Security updates |
|---|---|
| 4.0.x | ✅ |
| < 4.0 | ❌ |

### Reporting a vulnerability

Please do **not** report security vulnerabilities as a public issue.

Use GitHub's private reporting instead: in the repository under **Security → Report a vulnerability**. Helpful details:

- affected version or commit
- description and impact
- steps to reproduce, ideally with an example request
- a suggested fix, if you have one

You will get a first response within 7 days. The project is maintained in spare time, so a fix may take a while. Once fixed, the vulnerability is published in the [CHANGELOG](CHANGELOG.md) and as a GitHub Security Advisory. You will be credited there if you wish.

### Scope

Of particular interest:

- bypassing the API key check or `TRUSTED_IPS`
- access to files outside `recordings/`
- injecting commands or arguments into SDR and decoder processes
- XSS or formula injection via received radio data (APRS, POCSAG, AIS, transcripts)
- secrets ending up in images, logs or exports

Installations run against the guidance in [docs/security.md](docs/security.md#english-version), for example with `ALLOW_INSECURE=true` or exposed to the internet without a reverse proxy, are out of scope.
