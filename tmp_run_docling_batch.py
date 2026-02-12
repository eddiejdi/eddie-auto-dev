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
                if hasattr(doc, 'title'):
                    obj['title'] = getattr(doc,'title')
                if hasattr(doc, 'export_to_text'):
                    try:
                        obj['text'] = doc.export_to_text()
                    except Exception:
                        obj['text'] = ''
                elif hasattr(doc,'text'):
                    obj['text'] = getattr(doc,'text')
                if hasattr(doc,'pages'):
                    obj['pages'] = getattr(doc,'pages')
            else:
                obj['_raw'] = str(res)
            with open(outp, 'w', encoding='utf-8') as wf:
                json.dump(obj, wf, ensure_ascii=False)
            print('WROTE', outp)
        except Exception as e:
            print('FAILED', src, e)
            traceback.print_exc()
