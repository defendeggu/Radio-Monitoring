"""
Connections to contest software.

- leader   one API process owns a listening socket (Redis lock with TTL)
- n1mm     N1MM+ UDP broadcasts: QSOs into the worked log, TX state for blanking
- cluster  DX cluster telnet server: skimmer spots for the N1MM+ bandmap
"""
