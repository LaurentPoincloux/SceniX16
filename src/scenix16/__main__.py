"""Point d'entrée : `python -m scenix16` et exécutable portable."""

import sys

from scenix16.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
