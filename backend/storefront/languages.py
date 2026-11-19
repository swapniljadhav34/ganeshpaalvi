"""
English + all 22 languages of the Eighth Schedule of the Constitution of India.

(code, English name, name in its own script, writing direction)
The website's built-in words come from frontend/src/i18n/*.js; the Designer can override any
of them per language in "Translations" (storefront.UiTranslation).
"""

LANGUAGES = [
    ("en", "English", "English", "ltr"),
    ("hi", "Hindi", "हिन्दी", "ltr"),
    ("bn", "Bengali", "বাংলা", "ltr"),
    ("te", "Telugu", "తెలుగు", "ltr"),
    ("mr", "Marathi", "मराठी", "ltr"),
    ("ta", "Tamil", "தமிழ்", "ltr"),
    ("ur", "Urdu", "اردو", "rtl"),
    ("gu", "Gujarati", "ગુજરાતી", "ltr"),
    ("kn", "Kannada", "ಕನ್ನಡ", "ltr"),
    ("ml", "Malayalam", "മലയാളം", "ltr"),
    ("or", "Odia", "ଓଡ଼ିଆ", "ltr"),
    ("pa", "Punjabi", "ਪੰਜਾਬੀ", "ltr"),
    ("as", "Assamese", "অসমীয়া", "ltr"),
    ("mai", "Maithili", "मैथिली", "ltr"),
    ("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ", "ltr"),
    ("ks", "Kashmiri", "کٲشُر", "rtl"),
    ("ne", "Nepali", "नेपाली", "ltr"),
    ("sd", "Sindhi", "سنڌي", "rtl"),
    ("kok", "Konkani", "कोंकणी", "ltr"),
    ("doi", "Dogri", "डोगरी", "ltr"),
    ("mni", "Manipuri", "ꯃꯤꯇꯩꯂꯣꯟ", "ltr"),
    ("brx", "Bodo", "बड़ो", "ltr"),
    ("sa", "Sanskrit", "संस्कृतम्", "ltr"),
]

LANGUAGE_CHOICES = [(code, f"{native} — {english}") for code, english, native, _ in LANGUAGES]
CODES = {code for code, *_ in LANGUAGES}


def languages_payload():
    return [{"code": c, "name": e, "native": n, "dir": d} for c, e, n, d in LANGUAGES]
