#!/usr/bin/env python3
"""比較結果を、この端末のブラウザで閲覧する。待受は127.0.0.1のみ。"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from asr_comparison_metrics import collect
import re

PAGE = r'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>ローカルASR比較</title>
<style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 24px;background:#f6f7fa;color:#19253a}h1{font-size:28px}p{line-height:1.7}table{border-collapse:collapse;width:100%;background:white}td,th{padding:14px;text-align:left;border-bottom:1px solid #ddd}.chart{display:flex;align-items:end;gap:25px;height:220px;margin:30px 0 55px}.col{flex:1;position:relative;text-align:center}.bar{background:#588cda;border-radius:8px 8px 0 0;min-height:2px}.value{padding:8px}.label{position:absolute;top:100%;width:100%;padding-top:8px}.card{background:white;padding:20px;border-radius:12px;margin:12px 0;white-space:pre-wrap;line-height:1.8}.muted{color:#626b7a}select,button{font:inherit;padding:8px;margin-right:8px}audio{width:100%}</style>
<h1>Fox・ローカルASR比較</h1><p>日本語の正解付き音声32件による予備比較と、実会議での確認。文字誤り率は低いほど良い。会議の全文には人手の正解データがないため、全文の精度順位は未確定。</p>
<p class="muted">Whisperは既存asr-workerと同じ生成設定へ揃えて再測定し、正式な結果だけを掲載しています。</p><div id="chart" class="chart"></div><table><thead><tr><th>モデル</th><th>文字誤り率</th><th>公開音声32件</th><th>会議10分</th><th>旧崩壊区間20分</th><th>全長95分</th></tr></thead><tbody id="metrics"></tbody></table>
<p class="muted">時間はモデル読み込みと事前の音声処理を除く。WhisperはASRのみ、MOSSはモデル内の時刻・話者出力を含む。実会議は同一録音・16kHz mono・highpass 60Hz・loudnorm。MOSSとWhisperは公式の長尺処理。CohereとBuzzは発話間で30秒以内に区切る。CohereとBuzzの話者・文字の時刻は未対応。MOSSの全長は発話間で10分以内の11入力に分割し、30秒を重ねる。話者IDは入力内だけで有効。</p>
<h2>実会議の出力と資源</h2><table><thead><tr><th>モデル・区間</th><th>出力文字数</th><th>壊れた文字</th><th>CUDA最大確保 / 予約</th><th>VAD区間の重なり</th></tr></thead><tbody id="resources"></tbody></table><p class="muted">壊れた文字は生成出力内のU+FFFD。CUDA確保量はPyTorchの記録で、物理VRAM使用量とは異なる。WhisperはCTranslate2のため未計測。VAD区間の重なりは発話欠落率や時刻の正解率を示さない。モデルごとに出力区間の粒度も異なり、精度順位には使わない。</p>
<p id="memory-observation" class="muted"></p>
<details><summary>その他の実測値を見る</summary><pre id="all-metrics"></pre></details><h2>生成設定を変えた対照実験</h2><p id="buzz-control">反復制限を外した出力を待っています。</p><p id="whisper-control"></p>
<h2>正解付き音声の出力を比べる</h2><select id="sample"></select><div id="reference" class="card"></div><div id="texts"></div>
<h2>会議の出力を確認する</h2><select id="suite"><option value="10min">冒頭10分</option><option value="recovery">旧崩壊区間・33分20秒〜53分20秒</option><option value="full">全長</option></select><select id="engine"></select><button id="load">表示</button><audio id="audio" controls src="/meeting.mp3"></audio><div id="meeting" class="card"></div>
<p id="status" class="muted"></p>
<script>
const names={whisper:'Whisper large-v3',cohere:'Cohere Transcribe',moss:'MOSS 0.9B',buzz:'BuzzASR Japanese','buzz-plain':'BuzzASR（反復制限なし）','whisper-plain':'Whisper（反復制限なし）'};const candidates=['whisper','cohere','moss','buzz'];let data={};
const $=id=>document.getElementById(id);const fmt=r=>r?`${r.wall_seconds.toFixed(1)}秒`:'未完了';
function showSample(){let i=Number($('sample').value);const sample=data.samples[i];$('reference').textContent=sample?'正解：'+sample.reference:'正解音声の準備中';$('texts').replaceChildren();for(const e of Object.keys(names)){let r=data.reports[e+'-fleurs'];let card=document.createElement('div');card.className='card';card.textContent=names[e]+'\n'+(r?.results[i]?.text??(data.failures[e+'-fleurs']?'この設定の測定は失敗：'+data.failures[e+'-fleurs'].error:e==='cohere'?'モデル取得条件への同意待ち':'結果待ち'));$('texts').append(card)}}
function showMeeting(){const e=$('engine').value,s=$('suite').value,r=data.reports[e+'-'+s];$('meeting').textContent=r?r.results.map(x=>x.segments?x.segments.map(t=>`[${(x.start+t.start).toFixed(1)}〜${(x.start+t.end).toFixed(1)} ${x.part?'入力'+x.part+' ':''}${t.speaker??'話者未対応'}] ${t.text}`).join('\n'):`[入力区間 ${x.start.toFixed(1)}〜${x.end.toFixed(1)}秒・文字の時刻は未対応] ${x.text}`).join('\n\n'):data.failures[e+'-'+s]?'測定失敗：'+data.failures[e+'-'+s].error+'\n未完了の生成出力：\n'+data.failures[e+'-'+s].partial_text:'結果待ち';$('audio').currentTime=s==='recovery'?2000:0}
async function refresh(){data=await(await fetch('/data')).json();$('metrics').replaceChildren();$('chart').replaceChildren();for(const e of candidates){let r=data.reports[e+'-fleurs'];let row=document.createElement('tr');for(const text of [names[e],r?(r.cer*100).toFixed(2)+'%':e==='cohere'?'同意待ち':'未完了',fmt(r),...['10min','recovery','full'].map(s=>fmt(data.reports[e+'-'+s])+(s==='full'&&!data.reports[e+'-'+s]&&data.progress[e]?`（${data.progress[e]}入力まで完了）`:''))]){let td=document.createElement('td');td.textContent=text;row.append(td)}$('metrics').append(row);let col=document.createElement('div');col.className='col';let value=document.createElement('div');value.className='value';value.textContent=r?(r.cer*100).toFixed(2)+'%':'未完了';let bar=document.createElement('div');bar.className='bar';bar.style.height=(r?(r.cer*100/Math.max(30,...Object.values(data.reports).filter(v=>Number.isFinite(v.cer)).map(v=>v.cer*100)))*170:0)+'px';let label=document.createElement('div');label.className='label';label.textContent=names[e];col.append(value,bar,label);$('chart').append(col)}if(!$('sample').options.length){data.samples.forEach((s,i)=>{let o=document.createElement('option');o.value=i;o.textContent=`音声 ${i+1}（ID ${s.id}）`;$('sample').append(o)})}showResources();showSample();$('status').textContent='更新：'+new Date().toLocaleString('ja-JP')+'。未完了の欄を成功扱いしません。'}
function showResources(){const wp=data.metrics['whisper-plain-fleurs'],wr=data.metrics['whisper-plain-recovery'];$('whisper-control').textContent=wp?`Whisperの文字誤り率：既存 ${(data.metrics['whisper-fleurs'].cer*100).toFixed(2)}% → 反復制限なし ${(wp.cer*100).toFixed(2)}%。`+(wr?` 会議20分の壊れた文字：${data.metrics['whisper-recovery'].replacement_chars}個 → ${wr.replacement_chars}個。`:''):'';$('all-metrics').textContent=JSON.stringify(data.metrics,null,2);const observation=data.memory_observation;if(observation){const processes=Array.isArray(observation.processes)?observation.processes:[observation.processes];$('memory-observation').textContent='MOSS全長の実行中、WindowsのGPU Process Memoryで共有GPUメモリ '+(processes.reduce((n,p)=>n+Number(p.SharedUsage),0)/2**30).toFixed(2)+'GiB を観測（'+new Date(observation.observed_at).toLocaleString('ja-JP')+'）。瞬間値であり最大値ではありません。';} $('resources').replaceChildren();for(const [key,v]of Object.entries(data.metrics)){if(v.suite==='fleurs'||key.includes('pilot'))continue;let row=document.createElement('tr');for(const text of [names[key.replace(/-(10min|recovery|full)$/,'')]+' / '+({full:'全長',recovery:'20分', '10min':'10分'}[v.suite]),v.chars+'文字',v.replacement_chars+'個',v.engine==='whisper'?'未計測':(v.torch_peak_allocated_mib/1024).toFixed(2)+' / '+(v.torch_peak_reserved_mib/1024).toFixed(2)+'GiB',v.vad_interval_coverage===undefined?'時刻未対応':(v.vad_interval_coverage*100).toFixed(2)+'%']){let td=document.createElement('td');td.textContent=text;row.append(td)}$('resources').append(row)}const official=data.metrics['buzz-fleurs'],plain=data.metrics['buzz-plain-fleurs'],recovery=data.metrics['buzz-plain-recovery'];$('buzz-control').textContent=plain?`正解音声32件の文字誤り率：公式 ${(official.cer*100).toFixed(2)}% → 制限なし ${(plain.cer*100).toFixed(2)}%。壊れた文字：${official.replacement_chars}個 → ${plain.replacement_chars}個。`+(recovery?` 会議20分の壊れた文字：${data.metrics['buzz-recovery'].replacement_chars}個 → ${recovery.replacement_chars}個。`:''):data.failures['buzz-plain-fleurs']?'Buzzは反復制限を外すと正解音声 ID '+data.failures['buzz-plain-fleurs'].input.id+' で出力上限に達して停止。32件の誤り率は未算出。'+(data.failures['buzz-plain-recovery']?' 会議20分の比較も出力上限で停止。':data.metrics['buzz-plain-recovery']?` 会議20分の壊れた文字：43個 → ${data.metrics['buzz-plain-recovery'].replacement_chars}個。`:''):'反復制限を外した出力を待っています。';}
for(const [e,n]of Object.entries(names)){let o=document.createElement('option');o.value=e;o.textContent=n;$('engine').append(o)}$('sample').onchange=showSample;$('load').onclick=showMeeting;refresh();setInterval(refresh,10000);
</script></html>'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--audio', required=True, type=Path)
    p.add_argument('--port', type=int, default=18881)
    args = p.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                body, kind = PAGE.encode(), 'text/html; charset=utf-8'
            elif self.path == '/data':
                reports = {}
                failures = {}
                for engine in ('whisper', 'cohere', 'moss', 'buzz', 'buzz-plain', 'whisper-plain'):
                    for suite in ('fleurs', '10min', 'recovery', 'full'):
                        f = args.root / f'{engine}-{suite}.json'
                        if f.exists():
                            reports[f'{engine}-{suite}'] = json.loads(f.read_text(encoding='utf-8'))
                        f = args.root / f'{engine}-{suite}-failure.json'
                        if f.exists():
                            failures[f'{engine}-{suite}'] = json.loads(f.read_text(encoding='utf-8'))
                f = args.root / 'fleurs.json'
                samples = json.loads(f.read_text(encoding='utf-8'))['samples'] if f.exists() else []
                progress = {}
                for engine in ('whisper', 'cohere', 'moss', 'buzz'):
                    f = args.root / f'{engine}-full-partial.json'
                    if f.exists():
                        progress[engine] = len(json.loads(f.read_text(encoding='utf-8')))
                f = args.root / 'moss-full-memory-observation.json'
                observation = json.loads(f.read_text(encoding='utf-8')) if f.exists() else None
                body = json.dumps({'reports': reports, 'samples': samples, 'progress': progress, 'failures': failures,
                                   'metrics': collect(args.root), 'memory_observation': observation}, ensure_ascii=False).encode()
                kind = 'application/json; charset=utf-8'
            elif self.path == '/meeting.mp3':
                size = args.audio.stat().st_size
                first, last = 0, size-1
                requested = self.headers.get('Range')
                if requested:
                    match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
                    if not match or not any(match.groups()):
                        self.send_error(416)
                        return
                    a, b = match.groups()
                    if a:
                        first, last = int(a), min(int(b), size-1) if b else size-1
                    else:
                        first = max(0, size-int(b))
                    if first > last or first >= size:
                        self.send_response(416)
                        self.send_header('Content-Range', f'bytes */{size}')
                        self.end_headers()
                        return
                with args.audio.open('rb') as audio:
                    audio.seek(first)
                    body = audio.read(last-first+1)
                self.send_response(206 if requested else 200)
                self.send_header('Content-Type', 'audio/mpeg')
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Length', str(len(body)))
                if requested:
                    self.send_header('Content-Range', f'bytes {first}-{last}/{size}')
                self.end_headers()
                self.wfile.write(body)
                return
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    print(f'比較画面 http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
