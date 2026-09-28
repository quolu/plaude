出典: https://huggingface.co/BuzzASR/japanese/raw/a64b1cf652ba0eb73a9671b0462d142b2c9b17b3/README.md
取得日: 2026-09-28
確度: モデル提供者の一次資料。記載の性能は提供者評価であり、本比較の実測とは区別する。

---

---
language: ja
license: mit
library_name: transformers
pipeline_tag: automatic-speech-recognition
base_model: openai/whisper-large-v3
tags: [automatic-speech-recognition, whisper, japanese, buzzasr]
datasets: [google/fleurs]
metrics: [cer, wer]
---

# BuzzASR — Japanese

A monolingual automatic speech recognition model for **Japanese**, fine-tuned from
[openai/whisper-large-v3](https://huggingface.co/openai/whisper-large-v3). Part of **BuzzASR**,
a suite of 102 language-specialized ASR models
([paper: arXiv:2609.09554](https://arxiv.org/abs/2609.09554), Findings of EMNLP 2026).

This model uses **full fine-tuning (native per-language tokenizer replacement + text multitask fine-tuning)**.

> 🏆 **State-of-the-art (open-source).** On the combined FLEURS + Common Voice test set, this model
> achieves the lowest CER of every open system we compare against: Whisper-large-v3, Omnilingual 1B/7B, MMS, Qwen3-ASR, and Cohere Transcribe.

## Results (normalized CER / WER, %)

| Test set | CER | WER | Whisper-large-v3 (zero-shot) CER |
|---|---|---|---|
| FLEURS | 14.49 | 125.06 | 9.82 |
| Common Voice 25 | 26.58 | 92.45 | 29.5 |
| Combined | 21.08 | 108.72 | 23.34 |

~1.1x CER reduction over Whisper zero-shot on the combined test set.

## Usage

```python
import torch, torchaudio
from transformers import WhisperForConditionalGeneration, WhisperProcessor

model = WhisperForConditionalGeneration.from_pretrained("BuzzASR/japanese", torch_dtype=torch.float16).to("cuda").eval()
proc  = WhisperProcessor.from_pretrained("BuzzASR/japanese")

wav, sr = torchaudio.load("audio.wav")           # 16 kHz mono
feats = proc(wav[0], sampling_rate=16000, return_tensors="pt").input_features.to("cuda").half()
ids = model.generate(feats, num_beams=1, no_repeat_ngram_size=3, repetition_penalty=1.2)
print(proc.batch_decode(ids, skip_special_tokens=True)[0])
```
The language/task prompt is baked into the generation config, so no `language=` argument is needed.

## Training data
[FLEURS](https://huggingface.co/datasets/google/fleurs) + **Common Voice Corpus 25.0** (Mozilla, March 2025; https://commonvoice.mozilla.org/en/datasets), capped per the paper. Text-only data from the **Goldfish** corpus (Chang et al., 2026).

## Limitations
Monolingual (Japanese only). Evaluated on FLEURS / Common Voice test splits; other domains or dialects may differ.

## Links & citation
- **Paper:** https://arxiv.org/abs/2609.09554 (Findings of EMNLP 2026)
- **Project page:** https://lemn-lab.github.io/buzz-asr/
- **All models:** https://huggingface.co/BuzzASR

```bibtex
@misc{buzzasr2026,
  title         = {BuzzASR: A Swarm of 100+ Monolingual Speech Recognition Models},
  author        = {Shivam Singh and Aditya Yadavalli and Catherine Arnett and Alex Warstadt},
  year          = {2026},
  eprint        = {2609.09554},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CL},
  note          = {Findings of the Association for Computational Linguistics: EMNLP 2026},
  url           = {https://arxiv.org/abs/2609.09554}
}
```
