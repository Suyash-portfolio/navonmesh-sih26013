"""
NAVONMESH - Module 4: Multilingual Semantic Attribute Linkage
FR-4 Specification:
- Hierarchical Scope Locking: Constrains search within District -> Taluk -> Village -> Parent Survey Number.
- Phonetic Tokenization: IndicSoundex combined with Levenshtein fuzzy distance to match Hindi/Marathi/Telugu names against municipal English property registries.
- Area Variance Ratio: Computes exact delta: DeltaArea = |Area_Legal - Area_Surveyed| / Area_Legal.
"""

import unicodedata
from typing import Dict, Any, List, Optional, Tuple


class IndicSoundexMatcher:
    """
    Phonetic tokenization and transliteration matcher optimized for Indian names
    across Devanagari (Hindi/Marathi), Telugu, and English latin transliterations.
    """
    DEV_TO_LATIN = {
        'क': 'K', 'ख': 'KH', 'ग': 'G', 'घ': 'GH', 'ङ': 'NG',
        'च': 'CH', 'छ': 'CHH', 'ज': 'J', 'झ': 'JH', 'ञ': 'NY',
        'ट': 'T', 'ठ': 'TH', 'ड': 'D', 'ढ': 'DH', 'ण': 'N',
        'त': 'T', 'थ': 'TH', 'द': 'D', 'ध': 'DH', 'न': 'N',
        'प': 'P', 'फ': 'PH', 'ब': 'B', 'भ': 'BH', 'म': 'M',
        'य': 'Y', 'र': 'R', 'ल': 'L', 'व': 'V', 'श': 'SH',
        'ष': 'SH', 'स': 'S', 'ह': 'H', 'ळ': 'L', 'क्ष': 'KSH', 'ज्ञ': 'DNY',
        'ा': 'A', 'ि': 'I', 'ी': 'I', 'ु': 'U', 'ू': 'U', 'े': 'E', 'ै': 'AI', 'ो': 'O', 'ौ': 'AU', 'ं': 'N',
        'अ': 'A', 'आ': 'A', 'इ': 'I', 'ई': 'I', 'उ': 'U', 'ऊ': 'U', 'ए': 'E', 'ऐ': 'AI', 'ओ': 'O', 'औ': 'AU',
        '्': ''
    }

    @staticmethod
    def transliterate_devanagari(text: str) -> str:
        """Transliterates Devanagari script to Latin phonetic string."""
        res = []
        for char in text:
            if char in IndicSoundexMatcher.DEV_TO_LATIN:
                res.append(IndicSoundexMatcher.DEV_TO_LATIN[char])
            elif char.isalnum() or char.isspace():
                res.append(char)
        return "".join(res).upper()

    @staticmethod
    def compute_soundex_code(name: str) -> str:
        """Computes Indic phonetic soundex hash."""
        name = IndicSoundexMatcher.transliterate_devanagari(name).upper().strip()
        if not name:
            return "Z000"

        soundex_map = {
            'B': '1', 'F': '1', 'P': '1', 'V': '1',
            'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
            'D': '3', 'T': '3',
            'L': '4',
            'M': '5', 'N': '5',
            'R': '6'
        }

        first_letter = name[0]
        tail = name[1:]
        digits = []

        for char in tail:
            code = soundex_map.get(char, '')
            if code and (not digits or code != digits[-1]):
                digits.append(code)

        digits_str = "".join(digits).ljust(3, '0')[:3]
        return f"{first_letter}{digits_str}"

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Standard dynamic programming Levenshtein distance."""
        s1 = s1.lower().strip()
        s2 = s2.lower().strip()
        if len(s1) < len(s2):
            return IndicSoundexMatcher.levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    @staticmethod
    def match_names(name_vernacular: str, name_english: str) -> Tuple[float, Dict[str, Any]]:
        """
        Calculates phonetic and fuzzy string similarity score (0.0 to 1.0)
        between vernacular Indian name and English property register name.
        """
        transliterated = IndicSoundexMatcher.transliterate_devanagari(name_vernacular)
        dist = IndicSoundexMatcher.levenshtein_distance(transliterated, name_english)
        max_len = max(len(transliterated), len(name_english), 1)
        levenshtein_similarity = max(0.0, 1.0 - (dist / max_len))

        soundex_v = IndicSoundexMatcher.compute_soundex_code(name_vernacular)
        soundex_e = IndicSoundexMatcher.compute_soundex_code(name_english)
        soundex_match = 1.0 if soundex_v == soundex_e else 0.8 if soundex_v[0] == soundex_e[0] else 0.2

        # Weighted semantic match score
        text_similarity = round(0.50 * levenshtein_similarity + 0.50 * soundex_match, 4)

        return text_similarity, {
            "name_vernacular": name_vernacular,
            "transliterated": transliterated,
            "name_english": name_english,
            "levenshtein_distance": dist,
            "levenshtein_similarity": round(levenshtein_similarity, 4),
            "soundex_vernacular": soundex_v,
            "soundex_english": soundex_e,
            "soundex_match": soundex_match,
            "s_text_score": text_similarity
        }


def compute_area_variance_ratio(area_legal: float, area_surveyed: float) -> float:
    """
    Computes exact delta: DeltaArea = |Area_Legal - Area_Surveyed| / Area_Legal
    """
    if area_legal <= 0:
        return 0.0
    return abs(area_legal - area_surveyed) / area_legal
