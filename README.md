# Garmin RSD — Clean Build (strict + heuristic)
- Strict core (`rsd_core_crc_plus.py`) fixes: skip 4B header magic; skip trailer + A1/B2 padding; respects `parsing_rules.json`; safe unpackers.
- Heuristic core (`rsd_core_signature.py`) for fast-track CSV track.
- GUI (`app.py`) with Auto fallback; one-shot runner (`one_test.py`) with strict timeout + fallback.

## Windows quick start
```bat
py -3 -m venv .venv
.\.venv\Scriptsctivate
pip install -r requirements.txt
python app.py
```
or
```bat
python one_test.py "C:\Temp\Your.RSD"
```
