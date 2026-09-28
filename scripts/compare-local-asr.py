#!/usr/bin/env python3
"""ローカルASR比較。録音と転写は指定した一時ディレクトリだけに保存する。"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import time
import unicodedata
import urllib.request

MODELS = {
    "cohere": ("CohereLabs/cohere-transcribe-03-2026", "b1eacc2686a3d08ceaae5f24a88b1d519620bc09"),
    "moss": ("OpenMOSS-Team/MOSS-Transcribe-Diarize", "704aa4a9c304e8520be88901e0d1960158ef5b15"),
    "buzz": ("BuzzASR/japanese", "a64b1cf652ba0eb73a9671b0462d142b2c9b17b3"),
    "whisper": ("Systran/faster-whisper-large-v3", "edaa852ec7e145841d8ffdb056a99866b5f0a478"),
}


def save(path, value):
    # 閲覧・回収が途中のJSONを読むことを防ぐ、ファイル境界の置換。
    pending = path.with_suffix('.json.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    pending.replace(path)


def normalize(text):
    return "".join(c.lower() for c in unicodedata.normalize("NFKC", text)
                   if unicodedata.category(c)[0] not in "PSZ" and not c.isspace())


def download(root, engine):
    from huggingface_hub import snapshot_download
    repo, revision = MODELS[engine]
    print(f"モデル取得: {engine} {revision}", flush=True)
    ignored = ["*.onnx", "demo/*"] + ([] if engine == "whisper" else ["*.bin"])
    path = snapshot_download(repo, revision=revision, ignore_patterns=ignored)
    save(root / f"model-{engine}.json", {"repo": repo, "revision": revision, "path": path})


def prepare(root):
    import soundfile as sf
    import torch
    from silero_vad import load_silero_vad, get_speech_timestamps
    import pyarrow.parquet as pq
    source = root / "meeting.mp3"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != "24e23ecaeabbfc2ad471f826854f02bd7825a3a21f83684b0f7fda24073d6352":
        raise ValueError("前回と録音が一致しない")
    wav = root / "meeting.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-ac", "1", "-ar", "16000",
                    "-af", "highpass=f=60,loudnorm", str(wav)], check=True)
    audio, sr = sf.read(wav, dtype="float32")
    if sr != 16000:
        raise ValueError("前処理のサンプルレート不一致")
    vad = get_speech_timestamps(torch.from_numpy(audio), load_silero_vad(), sampling_rate=sr,
                                max_speech_duration_s=28, min_silence_duration_ms=300,
                                speech_pad_ms=200, return_seconds=True)
    sf.write(root / "meeting-10min.wav", audio[:600*sr], sr)
    sf.write(root / "meeting-recovery.wav", audio[2000*sr:3200*sr], sr)
    save(root / "meeting-info.json", {"sha256": digest, "duration": len(audio)/sr, "vad": vad,
                                      "preprocess": "16k mono highpass=60 loudnorm"})
    for name, start, end in [("10min", 0, 600), ("recovery", 2000, 3200), ("full", 0, len(audio)/sr)]:
        chunks = []
        for v in vad:
            a, b = max(start, v["start"]), min(end, v["end"])
            if b > a:
                chunks.append({"start": a, "end": b})
        save(root / f"chunks-{name}.json", chunks)
    url = "https://huggingface.co/datasets/google/fleurs/resolve/refs%2Fconvert%2Fparquet/ja_jp/test/0000.parquet"
    parquet = root / "fleurs-ja-test.parquet"
    if not parquet.exists():
        urllib.request.urlretrieve(url, parquet)
    rows = pq.read_table(parquet).slice(0, 32).to_pylist()
    samples = []
    for i, row in enumerate(rows):
        raw = row["audio"]["bytes"]
        x, rate = sf.read(io.BytesIO(raw), dtype="float32")
        if rate != sr:
            raise ValueError("FLEURSのサンプルレート不一致")
        name = f"fleurs-{i:02}.wav"
        sf.write(root / name, x, rate)
        samples.append({"id": row["id"], "file": name, "reference": row["transcription"],
                        "duration": len(x)/rate})
    save(root / "fleurs.json", {"dataset": "google/fleurs ja_jp test", "url": url,
                               "selection": "先頭32件を固定・予備比較", "samples": samples})
    print(f"素材準備完了: {len(audio)/sr:.2f}秒・公開正解音声32件", flush=True)


def run(root, engine, suite, decoding="official"):
    if decoding != "official" and engine not in ("buzz", "whisper"):
        raise ValueError("生成設定の対照実験はBuzzとWhisperだけ")
    output_engine = engine if decoding == "official" else f"{engine}-{decoding}"
    os.environ["HF_HUB_OFFLINE"] = "1"
    import soundfile as sf
    import torch
    torch.set_num_threads(8)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDAが使用できない")
    from transformers import AutoProcessor, AutoModelForCausalLM, CohereAsrForConditionalGeneration, WhisperForConditionalGeneration
    info = json.loads((root / f"model-{engine}.json").read_text(encoding="utf-8"))
    path = info["path"]
    load_start = time.perf_counter()
    if engine == "whisper":
        # WindowsのCUDA DLLは公式PyTorch配布物から解決する。
        dll = os.add_dll_directory(str(Path(torch.__file__).parent / "lib")) if os.name == "nt" else None
        from faster_whisper import WhisperModel
        model = WhisperModel(path, device="cuda", compute_type="float16", local_files_only=True)
        def infer(x, filename):
            segs, _ = model.transcribe(x, language="ja", vad_filter=True, condition_on_previous_text=False,
                no_repeat_ngram_size=4 if decoding == "official" else 0,
                repetition_penalty=1.1 if decoding == "official" else 1.0, word_timestamps=True,
                hallucination_silence_threshold=2.0, temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0], hotwords=None)
            items = []
            for s in segs:
                items.append({"start": s.start, "end": s.end, "speaker": None, "text": s.text})
                if len(items) % 200 == 0:
                    print(f"Whisper生成中: {len(items)}セグメント・{s.end:.1f}秒まで", flush=True)
            return {"text": "".join(s["text"] for s in items), "segments": items}
    elif engine == "moss":
        from moss_transcribe_diarize import parse_transcript
        from moss_transcribe_diarize.inference_utils import build_transcription_messages, generate_transcription
        model = AutoModelForCausalLM.from_pretrained(path, trust_remote_code=True, dtype=torch.bfloat16,
                   attn_implementation="sdpa", local_files_only=True).to("cuda").eval()
        processor = AutoProcessor.from_pretrained(path, trust_remote_code=True, local_files_only=True)
        def infer(x, filename):
            def progress(n):
                if n % 1000 == 0:
                    print(f"MOSS生成中: {n}トークン", flush=True)
            r = generate_transcription(model, processor, build_transcription_messages(filename),
                   max_new_tokens=32768, do_sample=False, device=torch.device("cuda"), dtype=torch.bfloat16,
                   token_callback=progress)
            if r["generated_tokens"] >= 32768:
                raise RuntimeError("MOSSが出力トークン上限に到達")
            items = [{"start": s.start, "end": s.end, "speaker": s.speaker, "text": s.text}
                     for s in parse_transcript(r["text"])]
            return {"text": "".join(s["text"] for s in items), "segments": items,
                    "raw": r["text"], "tokens": r["generated_tokens"]}
    else:
        cls = CohereAsrForConditionalGeneration if engine == "cohere" else WhisperForConditionalGeneration
        dtype = torch.bfloat16 if engine == "cohere" else torch.float16
        model = cls.from_pretrained(path, dtype=dtype, local_files_only=True).to("cuda").eval()
        processor = AutoProcessor.from_pretrained(path, local_files_only=True)
        def infer(x, filename):
            inputs = processor(x, sampling_rate=16000, return_tensors="pt", **({"language": "ja"} if engine == "cohere" else {}))
            inputs = inputs.to("cuda", dtype=model.dtype)
            # Whisperは開始トークンを含め448位置。生成分は447まで。
            cap = 512 if engine == "cohere" else model.config.max_target_positions - 1
            kwargs = {"max_new_tokens": cap, "do_sample": False}
            if engine == "buzz" and decoding == "official":
                kwargs.update(num_beams=1, no_repeat_ngram_size=3, repetition_penalty=1.2)
            elif engine == "buzz":
                kwargs.update(num_beams=1, no_repeat_ngram_size=0, repetition_penalty=1.0)
            with torch.inference_mode():
                ids = model.generate(**inputs, **kwargs)
            eos = model.generation_config.eos_token_id
            eos_ids = eos if isinstance(eos, list) else [eos]
            decoded = (processor.decode(ids, skip_special_tokens=True) if engine == "cohere"
                       else processor.batch_decode(ids, skip_special_tokens=True))
            text = decoded if isinstance(decoded, str) else decoded[0]
            if ids.shape[-1] >= cap and ids[0, -1].item() not in eos_ids:
                save(root / f"{output_engine}-{suite}-failure.json",
                     {"engine": engine, "suite": suite, "decoding": decoding,
                      "error": "出力トークン上限に到達。完了結果ではない", "max_new_tokens": cap,
                      "input": job, "partial_text": text, "generated_ids": ids[0].tolist()})
                raise RuntimeError(f"{engine}が出力トークン上限に到達")
            result = {"text": text, "segments": None}
            if engine == "buzz" and "\ufffd" in text:
                # byte列が壊れた出力は原トークンも残し、文字列で補正しない。
                result["generated_ids"] = ids[0].tolist()
                result["generated_pieces"] = processor.tokenizer.convert_ids_to_tokens(ids[0].tolist())
            return result
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - load_start
    if suite == "fleurs":
        samples = json.loads((root / "fleurs.json").read_text(encoding="utf-8"))["samples"]
        jobs = [{**s, "start": 0, "end": s["duration"]} for s in samples]
    elif engine == "moss" and suite == "full":
        # Foxの実測では20分入力が物理VRAMを超えたため、10分以内にする。
        # 境界は発話間で選び、30秒を重ねる。話者番号は入力内だけで有効。
        whole, _ = sf.read(root / "meeting.wav", dtype="float32")
        vad = json.loads((root / "meeting-info.json").read_text(encoding="utf-8"))["vad"]
        gaps = [(a["end"]+b["start"])/2 for a,b in zip(vad, vad[1:]) if b["start"]-a["end"] >= .3]
        duration = len(whole)/16000
        boundaries = [0.0]
        while duration-boundaries[-1] > 570:
            candidates = [g for g in gaps if boundaries[-1]+500 <= g <= boundaries[-1]+570]
            if not candidates:
                raise RuntimeError("10分以内の長尺入力を作る発話間が見つからない")
            boundaries.append(min(candidates, key=lambda t: abs(t-boundaries[-1]-550)))
        boundaries.append(duration)
        jobs = []
        for part, (core_a,core_b) in enumerate(zip(boundaries,boundaries[1:])):
            a, b = max(0,core_a-15), min(duration,core_b+15)
            name = f"meeting-moss-part{part+1}.wav"
            sf.write(root / name, whole[round(a*16000):round(b*16000)], 16000)
            jobs.append({"file": name, "start": a, "end": b, "part": part+1,
                         "core_start": core_a, "core_end": core_b,
                         "speaker_scope": "入力ごと。全録音の話者ID統合なし"})
    elif engine in ("whisper", "moss"):
        filename = "meeting-10min.wav" if suite == "10min" else "meeting-recovery.wav" if suite == "recovery" else "meeting.wav"
        offset = 2000 if suite == "recovery" else 0
        x, _ = sf.read(root / filename, dtype="float32")
        jobs = [{"file": filename, "start": offset, "end": offset+len(x)/16000}]
    else:
        jobs = json.loads((root / f"chunks-{suite}.json").read_text(encoding="utf-8"))
        # 近接した発話は30秒枠内へまとめ、短い休止の前後の文脈を保つ。
        grouped = []
        for job in jobs:
            if (grouped and job["start"]-grouped[-1]["end"] <= 2
                    and job["end"]-grouped[-1]["start"] <= 28):
                grouped[-1]["end"] = job["end"]
            else:
                grouped.append(dict(job))
        jobs = grouped
    whole, _ = sf.read(root / "meeting.wav", dtype="float32")
    results = []
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    for i, job in enumerate(jobs):
        if "file" in job:
            filename = str(root / job["file"])
            x, _ = sf.read(filename, dtype="float32")
        else:
            x = whole[round(job["start"]*16000):round(job["end"]*16000)]
            filename = None
        started = time.perf_counter()
        r = infer(x, filename)
        torch.cuda.synchronize()
        if "core_start" in job:
            # 重複入力の全出力も残し、境界の所属を時間の中央で決める。
            r["raw_segments"] = r["segments"]
            r["segments"] = [s for s in r["segments"]
                             if job["core_start"] <= job["start"]+(s["start"]+s["end"])/2 < job["core_end"]]
            r["text"] = "".join(s["text"] for s in r["segments"])
        r.update(job)
        r["seconds"] = time.perf_counter() - started
        results.append(r)
        save(root / f"{output_engine}-{suite}-partial.json", results)
        print(f"{output_engine} {suite}: {i+1}/{len(jobs)} {r['seconds']:.2f}秒", flush=True)
    elapsed = time.perf_counter() - t0
    report = {"engine": engine, "suite": suite, "model": info, "load_seconds": load_seconds,
              "wall_seconds": elapsed, "torch_peak_allocated_mib": torch.cuda.max_memory_allocated()/2**20,
              "torch_peak_reserved_mib": torch.cuda.max_memory_reserved()/2**20,
              "environment": {"torch": torch.__version__, "gpu": torch.cuda.get_device_name(), "cuda": torch.version.cuda},
              "generation": ({"dtype": "float16", "beam_size": 5, "condition_on_previous_text": False, "vad_filter": True,
                  "no_repeat_ngram_size": 4 if decoding == "official" else 0,
                  "repetition_penalty": 1.1 if decoding == "official" else 1.0, "word_timestamps": True,
                  "hallucination_silence_threshold": 2.0, "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], "hotwords": None}
                             if engine == "whisper" else {"dtype": "float16", "num_beams": 1,
                                 "no_repeat_ngram_size": 3 if decoding == "official" else 0,
                                 "repetition_penalty": 1.2 if decoding == "official" else 1.0}
                             if engine == "buzz" else {"dtype": "bfloat16", "do_sample": False}),
              "decoding": decoding,
              "vocab_hints": False, "vocab_replacements": False,
              "chunking": ("VAD境界・最大28秒・2秒以内の休止を結合" if engine in ("buzz", "cohere") and suite != "fleurs"
                           else "発話間で10分以内・30秒重複・話者は入力内のみ" if engine == "moss" and suite == "full"
                           else "公開音声は1件ごと・実会議は公式長尺処理"),
              "results": results}
    if suite == "fleurs":
        import jiwer
        refs = [normalize(r["reference"]) for r in results]
        hyps = [normalize(r["text"]) for r in results]
        report["cer"] = jiwer.cer(refs, hyps)
        report["reference_chars"] = sum(map(len, refs))
    save(root / f"{output_engine}-{suite}.json", report)
    print(json.dumps({k:v for k,v in report.items() if k not in ("results", "model")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "download", "run"])
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--engine", choices=list(MODELS))
    p.add_argument("--suite", choices=["fleurs", "10min", "recovery", "full"])
    p.add_argument("--decoding", choices=["official", "plain"], default="official")
    args = p.parse_args()
    if args.action == "prepare":
        prepare(args.root)
    elif args.action == "download":
        download(args.root, args.engine)
    else:
        run(args.root, args.engine, args.suite, args.decoding)
