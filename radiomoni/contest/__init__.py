"""
Contest support: reference data, callsign checks, contest rules, the worked log
and the classification of spots (new multiplier, rare, dupe).

- callsign  structure check, base call, CQ WPX prefix
- refdata   cty.csv (country, zones), MASTER.SCP, Club Log Most Wanted (cached offline)
- rules     contest rules from rules/*.yaml (multipliers, bands, dupe scope)
- worked    worked log: ADIF / Cabrillo import and live QSOs from N1MM+
- engine    classify a spot against the active contest
- phonetic  callsigns from transcribed SSB speech (phonetic alphabet)
"""
