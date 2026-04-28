#langslist.py
# Part of SmartLingo addon for NVDA
# Based on SmartLingo's langslist.py

from languageHandler import getLanguageDescription
from logHandler import log
import addonHandler
addonHandler.initTranslation()

def g(code, short=False):
	"""Return a description for the language code passed as parameter."""
	if short and code == "auto":
		return _("Automatic")
	
	# Custom Roman variants
	if code == "ur_roman":
		return _("Urdu (Roman)")
	if code == "hi_roman":
		return _("Hindi (Roman)")
	if code == "bn_roman":
		return _("Bengali (Roman)")
	if code == "ne_roman":
		return _("Nepali (Roman)")

	if code in forced_codes:
		return forced_codes[code]
	res = getLanguageDescription(code)
	if res is not None: return res
	if code in needed_codes:
		return needed_codes[code]
	return code

forced_codes = {
	"ckb": _("Kurdish (Sorani)"),
}

needed_codes = {
	"auto": _("Automatically detect language"),
	"ak": _("Twi (Akan)"),
	"ay": _("Aymara"),
	"bho": _("Bhojpuri"),
	"bm": _("Bambara"),
	"ceb": _("Cebuano"),
	"doi": _("Dogri"),
	"ee": _("Ewe"),
	"eo": _("Esperanto"),
	"gom": _("Konkani"),
	"haw": _("Hawaiian"),
	"hmn": _("Hmong"),
	"ht": _("Creole Haiti"),
	"ilo": _("Ilocano"),
	"jv": _("Javanese"),
	"kri": _("Krio"),
	"ku": _("Kurdish"),
	"la": _("Latin"),
	"lg": _("Luganda"),
	"ln": _("Lingala"),
	"lus": _("Mizo"),
	"mai": _("Maithili"),
	"mg": _("Malagasy"),
	"mni-Mtei": _("Meiteilon (Manipuri)"),
	"my": _("Myanmar (Burmese)"),
	"ny": _("Chichewa"),
	"sd": _("Sindhi"),
	"sm": _("Samoan"),
	"sn": _("Shona"),
	"so": _("Somali"),
	"st": _("Sesotho"),
	"su": _("Sundanese"),
	"tl": _("Tagalog"),
	"yi": _("Yiddish"),
}

langcodes = [
	"auto",
	"af", "ak", "am", "ar", "as", "ay", "az", "be", "bg", "bho", "bm", "bn", "bn_roman",
	"bs", "ca", "ceb", "ckb", "co", "cs", "cy", "da", "de", "doi", "dv", "ee", "el", "en",
	"eo", "es", "et", "eu", "fa", "fi", "fil", "fr", "fy", "ga", "gd", "gl", "gn", "gom",
	"gu", "ha", "haw", "he", "hi", "hi_roman", "hmn", "hr", "ht", "hu", "hy", "id", "ig",
	"ilo", "is", "it", "ja", "jv", "ka", "kk", "km", "kn", "ko", "kri", "ku", "ky", "la",
	"lb", "lg", "ln", "lo", "lt", "lus", "lv", "mai", "mg", "mi", "mk", "ml", "mn", "mni-Mtei",
	"mr", "ms", "mt", "my", "ne", "ne_roman", "nl", "no", "nso", "ny", "om", "or", "pa", "pl",
	"ps", "pt", "qu", "ro", "ru", "rw", "sa", "sd", "si", "sk", "sl", "sm", "sn", "so", "sq",
	"sr", "st", "su", "sv", "sw", "ta", "te", "tg", "th", "ti", "tk", "tl", "tr", "ts", "tt",
	"ug", "uk", "ur", "ur_roman", "uz", "vi", "xh", "yi", "yo", "zh-CN", "zh-TW", "zu",
]

langslist = {}
for code in langcodes:
	name = g(code)
	try:
		oldName = langslist[name]
		# Avoid logging error for duplicate names if needed, but here it's fine
	except KeyError:
		langslist[name] = code
