# English case auxiliary model

This model is derived only from the public stock tessdata_best English model and synthetic images of the 500 words in ../english_words_500.txt. No uploaded user PDF, private transcript, phone number, or private numeric checkpoint is used for this model.

## Selected training run

- Source eng_best.traineddata SHA256: 8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba
- Output eng_case.traineddata SHA256: 424883a235d3bf33fc4accfbbee2f609535da4cc57228ce7f6da173ae6e52fbd
- 500 unique words, lowercase/uppercase/title case, DejaVu Sans/Serif 24px: 3,000 synthetic training lines.
- Tesseract 5.5.0, learning_rate=0.0001, 4,000 iterations.
- An additional four-face/two-size, 6,000-line, 8,000-iteration run did not improve the quality gates and was not selected.

## Deployment policy and validation

A full model replacement regressed recognition and is not deployed. The auxiliary model is used only for vocabulary words whose stock English confidence is below 75. It may change case only when the spelling matches case-insensitively, the output is lower/upper/title case, and auxiliary confidence is at least 94. Mixed-case identifiers, numbers, out-of-vocabulary words, and high-confidence stock output are kept. A proposed title-to-lowercase change also requires a glyph-height check that rejects a visibly capital initial.

- Calibration: Liberation Sans/Serif, 3,000 images: 2,990 → 2,991 exact case-sensitive words, no newly wrong output.
- Additional fonts: Noto Serif/Open Sans, 3,000 images: 2,993 → 2,995, no newly wrong output.
- Final additional faces: Liberation Sans Italic/DejaVu Sans Mono, 3,000 images: 2,989 → 2,991, no newly wrong output.
- Unseen 100 words, 600 images: 599/600 unchanged by the vocabulary guard.

These synthetic font tests are not a guarantee for every scan, size or handwriting. Confidence is a model score, not a calibrated probability. Source model license is retained in UPSTREAM_LICENSE.
