#!/bin/bash
# Quick Start Guide - Sistema LLM para Matching de Vagas

set -e

echo "════════════════════════════════════════════════════════════════════════════════"
echo "  🚀 QUICK START: Sistema LLM para Matching de Vagas"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Creating..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies if needed
if ! python3 -c "import requests" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -q requests
fi

echo "✅ Environment ready"
echo ""

# Configuration
export OLLAMA_HOST="${OLLAMA_HOST:-http://192.168.15.2:11434}"
export WHATSAPP_MODEL="${WHATSAPP_MODEL:-eddie-whatsapp:latest}"
export USE_LLM_COMPATIBILITY=1
export COMPATIBILITY_METHOD=hybrid
export COLLECT_TRAINING_DATA=1

echo "⚙️  Configuration:"
echo "   OLLAMA_HOST: $OLLAMA_HOST"
echo "   WHATSAPP_MODEL: $WHATSAPP_MODEL"
echo "   COMPATIBILITY_METHOD: $COMPATIBILITY_METHOD"
echo ""

# Show options
echo "════════════════════════════════════════════════════════════════════════════════"
echo "  📋 Choose an option:"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "  1. 🧪 Test LLM Compatibility (benchmark Jaccard vs LLM vs Hybrid)"
echo "  2. 📊 Collect Training Data (simulate 5 job applications)"
echo "  3. 📈 View Training Dashboard (stats and metrics)"
echo "  4. 💾 Export Training Dataset (generate JSONL for fine-tuning)"
echo "  5. 🔧 Fine-tune Model (retrain eddie-whatsapp with collected data)"
echo "  6. 🎯 Run Full Pipeline (test apply_real_job.py with LLM)"
echo "  7. 📖 Show Documentation (LLM_SYSTEM_README.md)"
echo "  8. 🔍 Interactive Demo (menu-driven)"
echo "  9. ❌ Exit"
echo ""
echo -n "Enter option (1-9): "
read option

case $option in
    1)
        echo ""
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo "  🧪 TEST: LLM Compatibility Benchmark"
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo ""
        python3 llm_compatibility.py
        ;;
    
    2)
        echo ""
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo "  📊 COLLECT: Training Data (5 demo runs)"
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo ""
        
        export DEMO_MODE=1
        export COMPATIBILITY_THRESHOLD=60.0
        
        for i in {1..5}; do
            echo "--- Sample $i/5 ---"
            python3 apply_real_job.py 2>&1 | grep -E "(DEMO MODE|Compatibilidade|enviado)" || true
            sleep 1
        done
        
        echo ""
        echo "✅ Training data collected. Showing stats..."
        python3 training_data_collector.py stats
        ;;
    
    3)
        echo ""
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo "  📈 DASHBOARD: Training Statistics"
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo ""
        python3 training_data_collector.py stats
        ;;
    
    4)
        echo ""
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo "  💾 EXPORT: Training Dataset"
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo ""
        python3 training_data_collector.py export
        
        if [ -f "/tmp/whatsapp_training_dataset.jsonl" ]; then
            echo ""
            echo "📄 Sample (first 3 entries):"
            head -3 /tmp/whatsapp_training_dataset.jsonl | python3 -m json.tool 2>/dev/null || head -3 /tmp/whatsapp_training_dataset.jsonl
        fi
        ;;
    
    5)
        echo ""
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo "  🔧 FINE-TUNE: Model Training"
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo ""
        
        # Check if training data exists
        if [ ! -f "/tmp/whatsapp_training_dataset.jsonl" ]; then
            echo "⚠️  No training data found. Collecting samples first..."
            echo ""
            
            export DEMO_MODE=1
            export COMPATIBILITY_THRESHOLD=60.0
            
            for i in {1..10}; do
                echo "--- Collecting sample $i/10 ---"
                python3 apply_real_job.py 2>&1 | grep -E "(DEMO MODE|Compatibilidade)" || true
                sleep 1
            done
            
            python3 training_data_collector.py export
        fi
        
        echo ""
        echo "🚀 Starting fine-tuning..."
        python3 finetune_whatsapp_model.py
        ;;
    
    6)
        echo ""
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo "  🎯 FULL PIPELINE: apply_real_job.py with LLM"
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo ""
        echo "Mode:"
        echo "  1. Demo Mode (simulated jobs)"
        echo "  2. Real Mode (WhatsApp groups)"
        echo ""
        echo -n "Choose (1-2): "
        read mode
        
        if [ "$mode" = "1" ]; then
            export DEMO_MODE=1
            export COMPATIBILITY_THRESHOLD=60.0
            echo ""
            echo "✅ Demo mode activated (threshold=60%)"
        else
            export DEMO_MODE=0
            echo ""
            echo -n "Compatibility threshold (recommended: 0.5-5.0): "
            read threshold
            export COMPATIBILITY_THRESHOLD="${threshold:-1.0}"
            echo "✅ Real mode activated (threshold=$COMPATIBILITY_THRESHOLD%)"
        fi
        
        echo ""
        echo "🚀 Running pipeline..."
        python3 apply_real_job.py
        ;;
    
    7)
        echo ""
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo "  📖 DOCUMENTATION"
        echo "════════════════════════════════════════════════════════════════════════════════"
        echo ""
        
        if command -v less &> /dev/null; then
            less LLM_SYSTEM_README.md
        else
            cat LLM_SYSTEM_README.md
        fi
        ;;
    
    8)
        echo ""
        echo "🔍 Launching interactive demo..."
        python3 llm_system_demo.py
        ;;
    
    9)
        echo ""
        echo "👋 Goodbye!"
        exit 0
        ;;
    
    *)
        echo ""
        echo "❌ Invalid option"
        exit 1
        ;;
esac

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "  ✅ Operation completed"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "📚 Documentation: LLM_SYSTEM_README.md"
echo "🔧 Interactive menu: python3 llm_system_demo.py"
echo "🧪 Quick test: python3 llm_compatibility.py"
echo ""
