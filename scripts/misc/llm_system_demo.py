#!/usr/bin/env python3
"""
Sistema Completo: LLM Compatibility + Fine-tuning
Demonstração e teste de todo o workflow
"""
import os
import sys


def print_banner(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def main():
    print_banner("🚀 SISTEMA LLM PARA MATCHING DE VAGAS")
    
    print("""
Este sistema implementa:

1️⃣  **LLM Compatibility Scoring** (shared-whatsapp)
   - Análise semântica de currículos vs vagas
   - Entende sinônimos (K8s = Kubernetes, SRE = DevOps)
   - Considera senioridade e contexto
   - 3 modos: LLM puro / Jaccard / Hybrid (70% LLM + 30% Jaccard)

2️⃣  **Coleta Automática de Dados de Treino**
   - SQLite tracking de todas as comparações
   - Feedback: emails enviados, aceitos, rejeitados
   - Correções manuais de scores
   - Export em formato JSONL para fine-tuning

3️⃣  **Fine-tuning Automático**
   - Re-treina modelo com feedback acumulado
   - Few-shot learning com melhores exemplos
   - Validação automática do novo modelo
   - Comparação antes/depois

4️⃣  **Integração Completa**
   - Substituição drop-in no apply_real_job.py
   - Variáveis de ambiente para controle
   - Fallback automático se LLM falhar
   - Logs detalhados de cada decisão
""")
    
    print_banner("📋 CONFIGURAÇÃO")
    
    # Environment variables
    env_vars = {
        "USE_LLM_COMPATIBILITY": os.environ.get("USE_LLM_COMPATIBILITY", "1"),
        "COMPATIBILITY_METHOD": os.environ.get("COMPATIBILITY_METHOD", "hybrid"),
        "COMPATIBILITY_THRESHOLD": os.environ.get("COMPATIBILITY_THRESHOLD", "75.0"),
        "COLLECT_TRAINING_DATA": os.environ.get("COLLECT_TRAINING_DATA", "1"),
        "OLLAMA_HOST": os.environ.get("OLLAMA_HOST", "http://192.168.15.2:11434"),
        "WHATSAPP_MODEL": os.environ.get("WHATSAPP_MODEL", "shared-whatsapp:latest"),
    }
    
    for key, value in env_vars.items():
        icon = "✅" if value in ["1", "hybrid", "shared-whatsapp:latest"] else "⚙️"
        print(f"   {icon} {key}={value}")
    
    print_banner("🧪 TESTES DISPONÍVEIS")
    
    print("""
Escolha uma opção:

1. Test LLM Compatibility (comparar métodos: Jaccard vs LLM vs Hybrid)
2. Collect Training Data (simular coleta de dados de treino)
3. Show Training Dashboard (métricas e estatísticas de treino)
4. Export Training Dataset (gerar JSONL para fine-tuning)
5. Fine-tune Model (re-treinar shared-whatsapp com dados coletados)
6. Run Full Pipeline (teste completo do apply_real_job.py)
7. Exit
""")
    
    choice = input("Opção (1-7): ").strip()
    
    if choice == "1":
        print_banner("🧪 TEST: LLM Compatibility")
        os.system("python3 llm_compatibility.py")
    
    elif choice == "2":
        print_banner("📊 COLLECT: Training Data")
        print("Executando 5 scans para coletar amostras de treino...")
        os.environ["COLLECT_TRAINING_DATA"] = "1"
        os.environ["USE_LLM_COMPATIBILITY"] = "1"
        os.environ["COMPATIBILITY_METHOD"] = "hybrid"
        os.environ["COMPATIBILITY_THRESHOLD"] = "75.0"
        os.environ["DEMO_MODE"] = "1"
        
        # Run 5 times to collect training samples
        for i in range(1, 6):
            print(f"\n--- Scan {i}/5 ---")
            os.system("python3 apply_real_job.py 2>&1 | tail -20")
        
        # Show stats
        os.system("python3 training_data_collector.py stats")
    
    elif choice == "3":
        print_banner("📊 DASHBOARD: Training Statistics")
        os.system("python3 training_data_collector.py stats")
    
    elif choice == "4":
        print_banner("💾 EXPORT: Training Dataset")
        os.system("python3 training_data_collector.py export")
        
        # Show sample
        import json
        try:
            with open("/tmp/whatsapp_training_dataset.jsonl", 'r') as f:
                lines = f.readlines()
                if lines:
                    print("\n📄 Sample (first entry):")
                    sample = json.loads(lines[0])
                    print(f"   Prompt: {sample['prompt'][:200]}...")
                    print(f"   Completion: {sample['completion'][:200]}...")
                    print(f"\n   Total: {len(lines)} training examples")
        except:
            print("⚠️  No dataset found")
    
    elif choice == "5":
        print_banner("🔧 FINE-TUNE: Model Training")
        
        # Check if training data exists
        import os.path
        if not os.path.exists("/tmp/whatsapp_training_dataset.jsonl"):
            print("⚠️  No training data found. Running option 2 (Collect Training Data) first...")
            print("\nPress Enter to continue or Ctrl+C to cancel...")
            input()
            # Collect data first
            os.environ["COLLECT_TRAINING_DATA"] = "1"
            os.environ["DEMO_MODE"] = "1"
            for i in range(1, 11):
                print(f"\n--- Collecting sample {i}/10 ---")
                os.system("python3 apply_real_job.py 2>&1 | tail -10")
            
            # Export
            os.system("python3 training_data_collector.py export")
        
        print("\n🚀 Starting fine-tuning process...")
        print("   This may take 2-5 minutes depending on model size...")
        os.system("python3 finetune_whatsapp_model.py")
    
    elif choice == "6":
        print_banner("🎯 FULL PIPELINE: apply_real_job.py")
        
        print("Modo de execução:")
        print("1. Demo Mode (simula vagas para teste)")
        print("2. Real Mode (busca vagas reais no WhatsApp)")
        
        mode = input("Escolha (1-2): ").strip()
        
        if mode == "1":
            os.environ["DEMO_MODE"] = "1"
            os.environ["COMPATIBILITY_THRESHOLD"] = "60.0"
            print("\n✅ Demo mode ativado (threshold=60%)")
        else:
            os.environ["DEMO_MODE"] = "0"
            threshold = input("Threshold de compatibilidade (sugerido: 0.5-5.0): ").strip() or "1.0"
            os.environ["COMPATIBILITY_THRESHOLD"] = threshold
            print(f"\n✅ Real mode ativado (threshold={threshold}%)")
        
        os.environ["USE_LLM_COMPATIBILITY"] = "1"
        os.environ["COMPATIBILITY_METHOD"] = "hybrid"
        os.environ["COLLECT_TRAINING_DATA"] = "1"
        
        print("\n🚀 Executando pipeline completo...\n")
        os.system("python3 apply_real_job.py")
    
    elif choice == "7":
        print("\n👋 Até logo!\n")
        sys.exit(0)
    
    else:
        print("❌ Opção inválida")
        sys.exit(1)
    
    # Ask to continue
    print("\n" + "=" * 80)
    print("Executar outra operação? (y/n): ", end='')
    if input().strip().lower() == 'y':
        main()
    else:
        print("\n👋 Até logo!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo usuário\n")
        sys.exit(0)
