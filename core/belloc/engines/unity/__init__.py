"""Агульнае для рухавікоў на Unity (UnityPy): чытанне і запіс бандлаў."""

# усталёўшчык (release.py): залежнасці UnityPy з данымі і dll — без іх exe падае пры чытанні тэкстур
PYINSTALLER = ["--collect-data", "UnityPy", "--collect-submodules", "UnityPy",
               *[x for m in ("fmod_toolkit", "pyfmodex", "archspec", "astc_encoder", "etcpak",
                             "texture2ddecoder", "tpk_ar")
                 for x in ("--collect-all", m)]]
