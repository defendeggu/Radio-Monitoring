"""
Contest skimmer: finds the active signals of a band segment, decodes them in
parallel and reports the callsigns as spots.

- activity   averaged FFT, noise floor, peaks and their tracks
- confirm    a callsign becomes a spot after repeated, plausible hits
- core       one decoder per signal (CW), scheduling of the decoders
- session    SDR session (mode "skimmer"): blanking, waterfall, storage, cluster, alerts
- recorder   IQ of the segment plus RBN reference spots for the offline evaluation
- evaluate   precision and recall against reference spots (python -m radiomoni.skimmer.evaluate)
"""
