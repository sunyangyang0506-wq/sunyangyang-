#!/usr/bin/env python3
"""Render a derived knowledge snapshot; no network access or model calls."""
import argparse, html, json
from pathlib import Path

def render(data):
    thoughts = data.get('thoughts', [])
    knowledge = data.get('knowledge', [])
    nodes = thoughts + knowledge
    ids = [n['id'] for n in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate node ID')
    allowed = set(ids)
    thought_ids = {n['id'] for n in thoughts}
    for k in knowledge:
        if not set(k.get('thought_ids', [])) <= thought_ids:
            raise ValueError('Unknown thought reference')
    for r in data.get('relations', []):
        if r['from'] not in allowed or r['to'] not in allowed:
            raise ValueError('Dangling relation')
    def esc(value):
        return html.escape(str(value), quote=True)
    def cards(items):
        return ''.join('<details open><summary>'+esc(n['title'])+' · '+esc(n['id'])+'</summary><p>'+esc(n.get('statement',''))+'</p><p>成立条件：'+esc(n.get('conditions','待补充'))+'</p><p>来源：'+esc(n.get('source','未提供'))+'</p><p>关联思路：'+esc(', '.join(n.get('thought_ids',[])))+'</p></details>' for n in items)
    rows = ''.join('<tr>'+''.join('<td>'+esc(r.get(k,''))+'</td>' for k in ('from','type','to','evidence'))+'</tr>' for r in data.get('relations', []))
    statuses = ''.join('<li>'+esc(k)+'：'+esc(v)+'</li>' for k,v in data.get('status',{}).items())
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(data.get('title','我的思维与知识'))+'</title><style>body{max-width:1000px;margin:32px auto;padding:0 18px;font:16px/1.7 system-ui;color:#172338;background:#f6f7fa}details{background:white;padding:18px;margin:12px 0;border:1px solid #dce2eb;border-radius:8px}summary{font-weight:650;cursor:pointer}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd5e1;padding:10px;text-align:left}p,td{overflow-wrap:anywhere}nav a{margin-right:20px}</style><h1>'+esc(data.get('title','我的思维与知识'))+'</h1><nav><a href="#thoughts">思路展开</a><a href="#knowledge">知识资产</a><a href="#relations">关系与证据</a><a href="#status">运行状态</a></nav><h2 id="thoughts">思路展开</h2>'+cards(thoughts)+'<h2 id="knowledge">知识资产</h2>'+cards(knowledge)+'<h2 id="relations">关系与证据</h2><table><tr><th>起点</th><th>关系</th><th>终点</th><th>依据</th></tr>'+rows+'</table><h2 id="status">运行状态</h2><ul>'+statuses+'</ul></html>'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    page = render(json.loads(args.input.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding='utf-8')
