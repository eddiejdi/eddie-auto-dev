#!/usr/bin/env python3
"""
Processa PDF usando Docling (IBM) para extrair texto e conteúdo
"""
import sys
from pathlib import Path

print("📄 Processando PDF com Docling...")
print("="*80)

pdf_path = "/tmp/whatsapp_pdf_nil.pdf"

try:
    from docling.document_converter import DocumentConverter
    
    print("✓ Docling carregado")
    print(f"✓ Processando: {pdf_path}")
    print()
    
    # Inicializar conversor
    converter = DocumentConverter()
    
    # Converter PDF
    result = converter.convert(pdf_path)
    
    print("="*80)
    print("CONTEÚDO EXTRAÍDO:")
    print("="*80)
    print()
    
    # Extrair texto
    if hasattr(result, 'document'):
        doc = result.document
        
        # Tentar diferentes métodos de extração
        if hasattr(doc, 'export_to_markdown'):
            text = doc.export_to_markdown()
            print(text)
        elif hasattr(doc, 'export_to_text'):
            text = doc.export_to_text()
            print(text)
        elif hasattr(doc, 'text'):
            print(doc.text)
        else:
            # Método genérico
            print(str(doc))
        
        # Salvar em arquivo
        output_file = "/tmp/whatsapp_pdf_content.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            if hasattr(doc, 'export_to_markdown'):
                f.write(doc.export_to_markdown())
            elif hasattr(doc, 'export_to_text'):
                f.write(doc.export_to_text())
            else:
                f.write(str(doc))
        
        print()
        print("="*80)
        print(f"✓ Conteúdo salvo em: {output_file}")
        
    else:
        print("⚠️  Formato de resultado não reconhecido")
        print(f"Tipo: {type(result)}")
        print(f"Atributos: {dir(result)}")
        print(str(result))
    
except ImportError as e:
    print(f"❌ Erro de importação: {e}")
    print("Tentando método alternativo...")
    
    # Fallback: tentar com PyMuPDF ou outro
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        print(f"✓ PDF aberto com PyMuPDF ({len(doc)} página(s))")
        print()
        
        for page_num, page in enumerate(doc, 1):
            print(f"--- Página {page_num} ---")
            text = page.get_text()
            
            if text.strip():
                print(text)
            else:
                print("(Página parece conter apenas imagens)")
        
        doc.close()
        
    except ImportError:
        print("❌ PyMuPDF também não disponível")
        print("Tentando OCR com Pillow...")
        
        try:
            from PIL import Image
            import pytesseract
            
            # Processar imagem extraída
            img_path = "/tmp/whatsapp_pdf_img-000.jpg"
            
            if Path(img_path).exists():
                print(f"✓ Processando imagem: {img_path}")
                
                img = Image.open(img_path)
                
                # Tentar OCR (pode falhar sem tesseract instalado)
                try:
                    text = pytesseract.image_to_string(img, lang='por')
                    print()
                    print("="*80)
                    print("TEXTO EXTRAÍDO (OCR):")
                    print("="*80)
                    print(text)
                    
                    # Salvar
                    with open("/tmp/whatsapp_pdf_content.txt", 'w') as f:
                        f.write(text)
                    
                except Exception as ocr_err:
                    print(f"⚠️  OCR falhou: {ocr_err}")
                    print("Tesseract pode não estar instalado no sistema")
            else:
                print(f"❌ Imagem não encontrada: {img_path}")
                
        except ImportError as pil_err:
            print(f"❌ Pillow não disponível: {pil_err}")

except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()

print()
print("="*80)
print("✓ Processamento concluído")
