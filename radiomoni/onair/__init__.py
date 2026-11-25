"""
OnAir (https://on-air.dev) as a separate receiver in the stack.

onair-server runs in its own container (compose profile "onair") and is driven
over its remote-control API. RadioMoni holds the SDR lock while OnAir has the
radio open, reads the decoded messages that OnAir writes as JSON lines into its
data volume, stores them (radio-onair-*), publishes them live and checks them
against the alert rules.

OnAir is GPL-3.0 with attribution terms and is not part of this repository:
Based on OnAir by Kristijonas Adomaitis - https://on-air.dev
"""

ATTRIBUTION = 'Based on OnAir by Kristijonas Adomaitis - https://on-air.dev'
CONTRIBUTORS_URL = 'https://github.com/adswill/OnAir/blob/main/CONTRIBUTORS.md'
