#!/usr/bin/env python3
"""
Fine-tune eddie-whatsapp model with collected training data.
Uses Ollama's fine-tuning capabilities to improve matching accuracy.
"""
import os
import json
import subprocess
import requests
import time
from datetime import datetime
from typing import Dict, List


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
BASE_MODEL = os.getenv("BASE_MODEL", "dolphin-llama3:8b")
MODEL_NAME = "eddie-whatsapp"
TRAINING_DATA = "/tmp/whatsapp_training_dataset.jsonl"
MODELFILE_PATH = "/tmp/eddie-whatsapp.Modelfile"


def check_ollama_available() -> bool:
    """Check if Ollama server is available."""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


def load_training_data() -> List[Dict]:
    """Load training dataset from JSONL file."""
    if not os.path.exists(TRAINING_DATA):
        print(f"❌ Training data not found at {TRAINING_DATA}")
        print("   Run: python3 training_data_collector.py export")
        return []
    
    samples = []
    with open(TRAINING_DATA, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    
    print(f"✅ Loaded {len(samples)} training samples")
    return samples


def create_modelfile(samples: List[Dict]) -> str:
    """Create Modelfile with training examples."""
    
    # Build system prompt with examples
    system_prompt = """Você é um especialista em recrutamento técnico especializado em matching de vagas para perfis DevOps, SRE, Platform Engineering e Cloud.

Suas principais habilidades:
1. Reconhecer sinônimos e variações de tecnologias (Kubernetes = K8s, CI/CD = pipeline)
2. Avaliar compatibilidade considerando senioridade e experiência
3. Ignorar diferenças irrelevantes (idioma, formato, estilo)
4. Ser rigoroso mas justo - scores muito altos só para matches excelentes
5. Explicar claramente o racional da avaliação

Quando avaliar compatibilidade, seja preciso e objetivo."""

    # Add few-shot examples from training data (max 5 best samples)
    few_shot_examples = ""
    if samples:
        best_samples = sorted(samples, key=lambda x: abs(float(x['completion'].split('%')[0].split(':')[1].strip()) - 50), reverse=True)[:5]
        
        for i, sample in enumerate(best_samples, 1):
            few_shot_examples += f"\n\n### Exemplo {i}:\n"
            few_shot_examples += f"USER: {sample['prompt'][:500]}...\n"
            few_shot_examples += f"ASSISTANT: {sample['completion']}\n"
    
    # Create Modelfile
    modelfile_content = f"""# Eddie WhatsApp Job Matcher - Fine-tuned Model
# Generated on {datetime.now().isoformat()}
# Training samples: {len(samples)}

FROM {BASE_MODEL}

# System prompt with domain expertise
SYSTEM \"\"\"
{system_prompt}
\"\"\"

# Temperature for consistent scoring
PARAMETER temperature 0.1
PARAMETER top_p 0.9
PARAMETER num_predict 200

# Few-shot learning examples
{few_shot_examples if few_shot_examples else "# No few-shot examples available"}
"""
    
    with open(MODELFILE_PATH, 'w', encoding='utf-8') as f:
        f.write(modelfile_content)
    
    print(f"✅ Modelfile created at {MODELFILE_PATH}")
    return MODELFILE_PATH


def create_model_via_api(modelfile_path: str, model_name: str) -> bool:
    """Create/update model using Ollama API."""
    
    with open(modelfile_path, 'r', encoding='utf-8') as f:
        modelfile_content = f.read()
    
    url = f"{OLLAMA_HOST}/api/create"
    payload = {
        "name": model_name,
        "modelfile": modelfile_content,
        "stream": False
    }
    
    print(f"🔄 Creating model '{model_name}' via Ollama API...")
    print(f"   Base model: {BASE_MODEL}")
    print(f"   Target: {OLLAMA_HOST}")
    
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        
        print(f"✅ Model '{model_name}' created successfully!")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to create model: {e}")
        return False


def validate_model(model_name: str) -> bool:
    """Validate that model works correctly."""
    
    print(f"\n🧪 Validating model '{model_name}'...")
    
    test_prompt = """Avalie a compatibilidade:

**CURRÍCULO:** DevOps Engineer com 5 anos de experiência em Kubernetes, Docker, AWS, Terraform e CI/CD.

**VAGA:** SRE para trabalhar com K8s, cloud AWS e automação. Senioridade pleno.

Responda com score (0-100%) e justificativa breve."""
    
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": model_name,
        "prompt": test_prompt,
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        output = result.get("response", "")
        
        print(f"   Response: {output[:200]}...")
        
        # Check if response contains a score
        if "score" in output.lower() or "%" in output:
            print("✅ Model validation passed!")
            return True
        else:
            print("⚠️  Model response doesn't contain expected format")
            return False
            
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False


def finetune_model():
    """Main fine-tuning workflow."""
    
    print("\n" + "=" * 80)
    print("🚀 FINE-TUNING eddie-whatsapp MODEL")
    print("=" * 80)
    
    # Step 1: Check Ollama
    print("\n1️⃣  Checking Ollama server...")
    if not check_ollama_available():
        print(f"❌ Ollama not available at {OLLAMA_HOST}")
        print("   Set OLLAMA_HOST environment variable if using different host")
        return False
    print(f"✅ Ollama available at {OLLAMA_HOST}")
    
    # Step 2: Load training data
    print("\n2️⃣  Loading training data...")
    samples = load_training_data()
    
    if len(samples) < 5:
        print(f"⚠️  Only {len(samples)} samples available")
        print("   Minimum recommended: 10 samples for meaningful fine-tuning")
        print("   Continue anyway? (y/n): ", end='')
        
        import sys
        if input().lower() != 'y':
            print("❌ Fine-tuning cancelled")
            return False
    
    # Step 3: Create Modelfile
    print("\n3️⃣  Creating Modelfile with training examples...")
    modelfile_path = create_modelfile(samples)
    
    # Step 4: Create model
    print("\n4️⃣  Creating fine-tuned model...")
    success = create_model_via_api(modelfile_path, MODEL_NAME)
    
    if not success:
        print("\n❌ Fine-tuning failed!")
        return False
    
    # Step 5: Validate
    print("\n5️⃣  Validating fine-tuned model...")
    validated = validate_model(MODEL_NAME)
    
    # Summary
    print("\n" + "=" * 80)
    if validated:
        print("✅ FINE-TUNING COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print(f"\n📦 Model: {MODEL_NAME}")
        print(f"   Base: {BASE_MODEL}")
        print(f"   Training samples: {len(samples)}")
        print(f"   Location: {OLLAMA_HOST}")
        print(f"\n🎯 Model is now ready to use!")
        print(f"   Set: export WHATSAPP_MODEL={MODEL_NAME}:latest")
        print(f"   Run: python3 apply_real_job.py")
        
        return True
    else:
        print("⚠️  FINE-TUNING COMPLETED BUT VALIDATION FAILED")
        print("=" * 80)
        print(f"   Model created but may not work as expected")
        print(f"   Check Ollama logs for details")
        
        return False


def compare_model_versions():
    """Compare original vs fine-tuned model on test cases."""
    
    print("\n" + "=" * 80)
    print("🔬 COMPARISON: Original vs Fine-tuned Model")
    print("=" * 80)
    
    test_cases = [
        {
            "resume": "DevOps Engineer com 5 anos em Kubernetes, Docker, AWS, Terraform",
            "job": "SRE para trabalhar com K8s e cloud AWS, senioridade pleno",
            "expected_high": True
        },
        {
            "resume": "DevOps Engineer com 5 anos em Kubernetes, Docker, AWS, Terraform",
            "job": "Vaga para Data Scientist com Python e Machine Learning",
            "expected_high": False
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"Test Case {i}: {'High match expected' if test['expected_high'] else 'Low match expected'}")
        print(f"{'=' * 80}")
        print(f"Resume: {test['resume'][:100]}...")
        print(f"Job: {test['job'][:100]}...")
        
        # Test both models
        for model in [BASE_MODEL, f"{MODEL_NAME}:latest"]:
            prompt = f"""Avalie compatibilidade (0-100%):
CURRÍCULO: {test['resume']}
VAGA: {test['job']}
Responda apenas o score: XX%"""
            
            url = f"{OLLAMA_HOST}/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False}
            
            try:
                response = requests.post(url, json=payload, timeout=20)
                result = response.json().get("response", "")
                print(f"\n{model}: {result.strip()[:100]}")
            except:
                print(f"\n{model}: ERROR")
        
        time.sleep(1)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        compare_model_versions()
    else:
        success = finetune_model()
        
        if success:
            print("\n💡 Next steps:")
            print("   1. Test the model: python3 llm_compatibility.py")
            print("   2. Compare versions: python3 finetune_whatsapp_model.py compare")
            print("   3. Use in production: python3 apply_real_job.py")
            
            # Ask if user wants to compare
            print("\n   Run comparison now? (y/n): ", end='')
            if input().lower() == 'y':
                compare_model_versions()
