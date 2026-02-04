"""Compatibility wrapper.

Older workflows call `python dashboard.py`.
The real implementation lives in `generate_dashboard.py`.
"""

import generate_dashboard

if __name__ == "__main__":
    generate_dashboard.generate_dashboard()
