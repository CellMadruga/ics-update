"""Atajo: solo el diagnóstico de caminar. Ver tools\\diag.py.

    python tools\\diag_caminar.py [--arreglar]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv += ["--caminar", "--solo-caminar"]

import diag   # noqa: E402

if __name__ == "__main__":
    diag.main()
