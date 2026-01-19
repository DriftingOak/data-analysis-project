import config

q = "Paramount x Warner Bros. acquisition announced by June 30?".lower()
matches = [kw for kw in config.GEO_KEYWORDS if kw in q]
print(f"Matches: {matches}")