"""Built-in 5×7 bitmap font – retro headings without shipping font files."""
import pygame

_G = {
    "A": "0E11111F111111", "B": "1E11111E11111E", "C": "0E11101010110E", "D": "1C12111111121C",
    "E": "1F10101E10101F", "F": "1F10101E101010", "G": "0E11101711110F", "H": "1111111F111111",
    "I": "0E04040404040E", "J": "0702020202120C", "K": "11121418141211", "L": "1010101010101F",
    "M": "111B1515111111", "N": "11111915131111", "O": "0E11111111110E", "P": "1E11111E101010",
    "Q": "0E11111115120D", "R": "1E11111E141211", "S": "0F10100E01011E", "T": "1F040404040404",
    "U": "1111111111110E", "V": "11111111110A04", "W": "1111111515150A", "X": "11110A040A1111",
    "Y": "1111110A040404", "Z": "1F01020408101F",
    "0": "0E11131519110E", "1": "040C040404040E", "2": "0E11010204081F", "3": "1F02040201110E",
    "4": "02060A121F0202", "5": "1F101E0101110E", "6": "0608101E11110E", "7": "1F010204080808",
    "8": "0E11110E11110E", "9": "0E11110F01020C",
    " ": "00000000000000", ".": "00000000000C0C", ",": "000000000C0408", ":": "000C0C000C0C00",
    "!": "04040404040004", "?": "0E110102040004", "-": "0000001F000000", "+": "0004041F040400",
    "/": "00010204081000", "'": "04040800000000", "(": "02040808080402", ")": "08040202020408",
    "%": "18190204081303", "&": "0C12140815120D", "Ä": "0A000E111F1111", "Ö": "0A000E1111110E",
    "Ü": "0A00111111110E", ">": "08040201020408", "<": "02040810080402", "_": "0000000000001F",
    "=": "00001F001F0000", "*": "0004150E150400", "#": "0A0A1F0A1F0A0A", "|": "04040404040404",
    "×": "00110A040A1100", "◆": "00040E1F0E0400", "▲": "0004040E0E1F00", "♥": "000A1F1F0E0400",
    "[": "0E08080808080E", "]": "0E02020202020E", "@": "0E11171517100E",
}
GLYPHS = {}
for ch, hexs in _G.items():
    hexs = hexs.replace(" ", "")
    GLYPHS[ch] = [int(hexs[i:i + 2], 16) for i in range(0, 14, 2)]

_cache = {}
TRANSLATE = str.maketrans({"É": "E", "È": "E", "Ê": "E", "Á": "A", "À": "A", "Ó": "O", "Í": "I", "Ú": "U",
                           "Ñ": "N", "Ç": "C", "–": "-", "—": "-", "·": "-", "’": "'"})


def normalize(text):
    return text.upper().replace("ß", "SS").translate(TRANSLATE)


def size(text, scale):
    n = len(normalize(text))
    return (max(0, n * 6 - 1) * scale, 7 * scale)


def render(text, scale, color, shadow=None):
    key = (text, scale, tuple(color), tuple(shadow) if shadow else None)
    surf = _cache.get(key)
    if surf is not None:
        return surf
    t = normalize(text)
    w, h = size(text, scale)
    off = scale // 2 + 1 if shadow else 0
    surf = pygame.Surface((max(1, w + off), h + off), pygame.SRCALPHA)
    layers = ([(shadow, off)] if shadow else []) + [(color, 0)]
    for col, o in layers:
        x = 0
        for ch in t:
            rows = GLYPHS.get(ch, GLYPHS["?"])
            for ry, bits in enumerate(rows):
                for cx in range(5):
                    if bits & (0x10 >> cx):
                        surf.fill(col, (x + cx * scale + o, ry * scale + o, scale, scale))
            x += 6 * scale
    if len(_cache) > 600:
        _cache.clear()
    _cache[key] = surf
    return surf
