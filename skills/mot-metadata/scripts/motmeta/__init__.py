"""motmeta - create / validate / report MoT (Israel Ministry of Transport) dataset metadata.

Implements "נוהל הכנה, תיעוד והפצה של קבצי מידע תחבורתי" v1.3 plus optional domain
profiles (on-board surveys v1.0, traffic-sensor monthly packages v1.02).

Pure Python 3.10+. Hard deps: openpyxl. Optional: pandas (faster CSV sampling),
pyshp + pyproj (shapefile fields / CRS / bbox), a Chromium browser (PDF rendering).
"""
__version__ = "0.1.0"
