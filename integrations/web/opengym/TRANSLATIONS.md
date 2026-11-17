# OpenGym preview label additions

`locale-additions.json` contains original translations of the 17 new preview
labels for all 25 non-English locales present in the reviewed OpenGym source.
The object keys are locale IDs; each nested key is the English source string used
by OpenGym's translation lookup. The existing Play, Pause and Paused entries are
not included and must not be overwritten.

The text describes an optional movement preview, its camera and playback controls,
and its separate anatomy attribution. The cycle notice states that previews do
not record workout results. `{current}` and `{total}` remain literal placeholders;
their order varies where required by the language.

Automated checks established exact locale/key parity, nonempty strings, unique
JSON keys and matching placeholder sets. These are model-authored contribution
translations, not professionally reviewed native-language copy. Maintainer review
of terminology and rendered controls remains appropriate; the technical parity
checks do not establish naturalness or screen-reader pronunciation in every locale.

Merge only absent entries into the corresponding locale modules. Keep the host's
current language subscription, number formatting and right-to-left behavior;
do not introduce a second language setting for the preview.
