"""Jetons de couleur et de taille issus du Design Book v0.40.

Les valeurs historiques viennent du classeur SceniX16 ; les compléments
proposés sont signalés. Les composants utilisent ces noms de rôle, jamais
des couleurs écrites en dur.
"""

# Surfaces
GROUND = "#121212"        # fond application (historique)
PANEL = "#1A1A1A"         # panneaux, emplacements (historique)
CELL = "#1E1E1E"          # contenus, tableaux (historique)
RAISED = "#232326"        # survol, élément actif (complément)

# Bordures
LINE = "#30343A"          # séparateurs (historique)
LINE_SOFT = "#2A2A2A"     # bordures discrètes (historique)
LINE_STRONG = "#3D4249"   # boutons secondaires (complément)

# Textes
TEXT = "#EAEAEA"          # texte principal (historique)
SILK = "#F2E9DA"          # libellés de façade (historique)
MUTED = "#A0A0A0"         # texte secondaire (historique)
DIM = "#6B6B6E"           # désactivé, INIT (complément)
INK = "#151515"           # texte sur couleur vive (historique)

# Marque
BRAND = "#FF5A1F"         # orange SceniX16

# Touches du step sequencer (groupes 1 à 4)
KEY_RED = "#FF4E3A"
KEY_ORANGE = "#FF9450"
KEY_YELLOW = "#FCE95C"
KEY_WHITE = "#F9FFFF"
KEY_GREY = "#999A9C"
LED_ON = "#F30400"
LED_OFF = "#5F1B13"

# Sections
SECTION_OUTPUT = "#4AFC9E"
SECTION_TRACKS = KEY_YELLOW
SECTION_SETLISTS = KEY_ORANGE

# États
OK = "#2ECC71"
OK_BG = "#1B2B1F"
BAD = "#E74C3C"
BAD_BG = "#2A1616"

# Polices (Barlow et IBM Plex Mono seront ajoutées plus tard ; repli Segoe UI)
FONT_UI = ["Segoe UI Variable Text", "Segoe UI"]
FONT_LABEL = ["Barlow Semi Condensed", "Segoe UI"]
FONT_MONO = ["IBM Plex Mono", "Cascadia Mono", "Consolas"]

# NEW SETLIST tant qu'il est inactif : identité orange sans aplat (contraste 5,37:1)
BRAND_INACTIVE_BG = "#2A1A12"
BRAND_INACTIVE_BORDER = "#6A301A"

# Dimensions (pixels effectifs)
TOP_BAR_HEIGHT = 56
RAIL_WIDTH = 208            # rail de navigation (section 07)
CONTENT_MAX_WIDTH = 1600    # largeur utile plafonnée sur grand écran (section 08)
STATUS_BAR_HEIGHT = 32
WINDOW_MIN_WIDTH = 1024
WINDOW_MIN_HEIGHT = 640
WINDOW_DEFAULT_WIDTH = 1280
WINDOW_DEFAULT_HEIGHT = 800
