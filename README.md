# MORPHEUS - Matrix Interface v5.0.2

## 📋 Sobre
IA com personalidade filosófica (Matrix), especialista em sobrevivencialismo, bushcraft e emergências. Interface estilo Matrix com busca de notícias em tempo real e memória persistente.

## 🚀 Funcionalidades
- 🤖 Chatbot com Mistral AI
- 📰 Notícias mundiais, Brasil e por tópicos
- 💾 Memória persistente (nomes, histórico, tópicos)
- 🌐 Interface Matrix responsiva
- 🎮 Comandos: `/clear`, `/mundo`, `/news [assunto]`

## 📦 Dependências
```bash
Flask>=2.2.3
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
```

## 🔧 Instalação Rápida
```bash
# Clone
git clone https://github.com/seu-usuario/morpheus-ai.git
cd morpheus-ai

# Instale
pip install flask requests beautifulsoup4 lxml

# Execute
python Morpheus-5.0.2.py
```

Acesse: `http://localhost:5000`

## 🎮 Comandos
| Comando | Descrição |
|---------|-----------|
| `/clear` | Limpar conversa |
| `/mundo` | Notícias mundiais |
| `/news [assunto]` | Buscar notícias |

**Tópicos pré-definidos:** `crise_alimentar`, `guerras`, `pandemia`, `desastre_natural`, `ciberataque`, `refugiados`, `greve`, `nuclear`, `climatico`, `virus`

## 📁 Arquivos
```
morpheus-ai/
├── Morpheus-5.0.2.py      # Código principal
├── chat_memory.brain      # Memória persistente
└── chat_context.json      # Contexto atual
```

## ⚙️ Personalização
```python
# Trocar modelo
MODEL = "mistral-large-latest"

# Adicionar tópicos
TOPICS["meu_topico"] = "palavras+chave"
TOPIC_NAMES["meu_topico"] = "Nome Amigável"
```

## 🔒 Segurança
⚠️ Use variáveis de ambiente para a API key:
```bash
export MISTRAL_API_KEY="sua-chave"
```

## 🐛 Problemas Comuns
```bash
# Dependências faltando
pip install flask requests beautifulsoup4 lxml

# Timeout nas notícias
# Tente novamente ou use /news com termos específicos
```

---

**🐍 MORPHEUS - Desperte para a realidade...**
