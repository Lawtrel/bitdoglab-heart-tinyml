# TinyML on BitDogLab

An academic project developed by **Leandro Alves dos Santos during Introduction to Artificial Intelligence classes**. It studies CNN training, INT8 quantization and local RP2040 inference using heart sounds.

The repository contains a local teaching application, firmware, preserved research code, bilingual paper sources and classroom slides. Murmur-present/absent predictions are not clinical diagnoses. Microphone acquisition remains experimental.

Use Python 3.12:

```sh
python -m venv .venv
# Activate .venv for your shell
python -m pip install -e .
heart-tinyml doctor
heart-tinyml serve
```

Choose an audio example, run inference on the PC, then optionally connect a board running the demo firmware and compare the same PCM samples over USB. No GPU, board or full TensorFlow installation is required for PC-only inference.

The application uses Ports and Adapters, dependency injection and repositories. HTTP, WAV decoding, LiteRT and serial communication are separate from the use cases. See [architecture](docs/architecture.md) and [Portuguese setup instructions](docs/quickstart.md).

The original digital replay evaluated 6,512 windows from 471 recordings and 122 patient groups. Board F1 was 0.694, recall 0.708 and accuracy 0.877. These are group-level measurements from the scientific firmware, not estimates of microphone accuracy. Historical evidence and the reorganized application remain distinct; see [results and limitations](docs/results.md).

```sh
python -m unittest discover -s tests -v
```

Project code is MIT licensed. Audio and other third-party resources retain their respective licenses and attribution requirements. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Updated teaching material and benchmark (27 October 2026)

The training cohort contained 2,066 recordings from 568 groups (28,340 windows). The six validation excerpts in the demo were not the training dataset. The Portuguese teaching package now contains 28 editable slides, a visual PDF, speaker notes and a ten-page mathematical guide. Technical terms remain in English.

The new batch-one validation benchmark separates TensorFlow CPU/RTX Float32 from TFLite reference CPU Float32/INT8 and the V3 RP2040 demonstration. CPU/RTX medians were 0.661/0.768 ms, while CPU reference Float32/INT8 medians were 1.347/1.932 ms. Float32/INT8 TFLite files occupy 7,984/5,264 bytes (34.1% reduction). These are scoped measurements from one session, not an isolated universal speedup claim or new patient-level test accuracy. See [protocol and evidence](docs/new-benchmark.md).
