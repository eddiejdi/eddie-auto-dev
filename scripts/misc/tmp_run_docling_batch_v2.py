#!/usr/bin/env python3
import os, json, traceback
from pathlib import Path
in_dir = '/home/homelab/gdrive_downloads'
out_dir = '/home/homelab/gdrive_docling_out'
os.makedirs(out_dir, exist_ok=True)
try:
    from docling.document_converter import DocumentConverter
    print('imported DocumentConverter')
except Exception as e:
    print('docling import failed', e)
    raise
conv = DocumentConverter()
for root,_,files in os.walk(in_dir):
    for f in files:
        src = os.path.join(root,f)
        rel = os.path.relpath(src,in_dir)
        outp = os.path.join(out_dir, rel + '.json')
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        try:
            res = conv.convert(src)
            obj = {}
            if hasattr(res, 'document'):
                doc = res.document
                title = getattr(doc, 'title', None)
                if title:
                    obj['title'] = title
                # text extraction
                text = ''
                try:
                    if hasattr(doc, 'export_to_text'):
                        text = doc.export_to_text()
                    elif hasattr(doc, 'export_to_markdown'):
                        text = doc.export_to_markdown()
                    elif hasattr(doc, 'text'):
                        text = getattr(doc, 'text') or ''
                except Exception:
                    text = ''
                obj['text'] = text
                # pages: coerce to strings
                pages = []
                try:
                    raw_pages = getattr(doc, 'pages', None)
                    if raw_pages:
                        for p in raw_pages:
                            if isinstance(p, dict):
                                pages.append(p.get('text',''))
                            else:
                                if hasattr(p, 'text'):
                                    pages.append(getattr(p,'text') or '')
                                else:
                                    pages.append(str(p))
                except Exception:
                    pages = []
                if pages:
                    obj['pages'] = pages
            else:
                obj['_raw'] = str(res)
            with open(outp, 'w', encoding='utf-8') as wf:
                json.dump(obj, wf, ensure_ascii=False)
            print('WROTE', outp)
        except Exception as e:
            print('FAILED', src, e)
            traceback.print_exc()
