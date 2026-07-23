from flask import Flask, request, jsonify, render_template_string
import json
import re
import os
import pickle
import warnings
from datetime import datetime
import requests
import urllib.parse
from bs4 import BeautifulSoup as soup
from urllib.request import urlopen, Request

warnings.filterwarnings("ignore", category=DeprecationWarning)

app = Flask(__name__)

# ===== CONFIGURACAO MISTRAL AI =====
API_KEY = "rlpDuSpi9iA4IuiGHD0TFX0kBQXALH7Y"
API_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-large-latest"

# URLs para notícias
WORLD_NEWS_URL = (
    "https://news.google.com/rss/topics/"
    "CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx1YlY4U0JYQjBMVUpTR2dKQ1VpZ0FQAQ?"
    "hl=pt-BR&gl=BR&ceid=BR:pt-419"
)

BRAZIL_NEWS_URL = (
    "https://news.google.com/rss/topics/"
    "CAAqJQgKIh9DQkFTRVFvSUwyMHZNREUxWm5JU0JYQjBMVUpTS0FBUAE?"
    "hl=pt-BR&gl=BR&ceid=BR%3Apt-419"
)

# ===== TÓPICOS PARA BUSCA DE NOTÍCIAS =====
TOPICS = {
    "crise_alimentar": "falta+de+alimentos+escassez+fome",
    "crise_energia": "apagao+falta+de+energia+racionamento",
    "crise_agua": "racionamento+falta+de+agua+seca",
    "guerras": "guerra+conflito+ataque+tensao",
    "terrorismo": "ataque+terrorista+atentado",
    "pandemia": "surto+doenca+epidemia+virus",
    "desastre_natural": "terremoto+furacao+inundacao",
    "colapso_economico": "crise+bancaria+hiperinflacao",
    "ciberataque": "ataque+cibernetico+ransomware",
    "refugiados": "refugiados+migracao+crise+humanitaria",
    "greve": "greve+paralisacao+manifestacao+caminhoneiro",
    "nuclear": "acidente+nuclear+radioativo",
    "climatico": "mudanca+climatica+evento+extremo",
    "petroleo": "petroleo+preco+opep+corte",
    "greve_caminhoneiros": "greve+caminhoneiro+paralisacao+bloqueio+estrada",
    "virus": "covid+h1n1+h5n1+ebola+hantavirus+surto+viral",
    "secas": "Secas e Estiagem",
    "tempestades": "Tempestades e Alagamentos",
    "terremotos": "Terremotos e Furacões"
}

# ===== Mapeamento de tópicos para exibição amigável =====
TOPIC_NAMES = {
    "crise_alimentar": "Crise Alimentar",
    "crise_energia": "Crise Energética",
    "crise_agua": "Crise Hídrica",
    "guerras": "Guerras e Conflitos",
    "terrorismo": "Terrorismo",
    "pandemia": "Pandemias",
    "desastre_natural": "Desastres Naturais",
    "colapso_economico": "Colapso Econômico",
    "ciberataque": "Ciberataques",
    "refugiados": "Refugiados",
    "greve": "Greves",
    "nuclear": "Acidentes Nucleares",
    "climatico": "Mudanças Climáticas",
    "petroleo": "Petróleo",
    "greve_caminhoneiros": "Greve dos Caminhoneiros",
    "virus": "Vírus"
}

MEMORY_FILE = "chat_memory.brain"
CONTEXT_FILE = "chat_context.json"

# ===== MEMORIA DE CONVERSA (igual ao her.py) =====

class ChatMemory:
    def __init__(self, memory_file=MEMORY_FILE, context_file=CONTEXT_FILE):
        self.memory_file = memory_file
        self.context_file = context_file
        self.conversation_history = []
        self.known_names = {"user": None, "pessoas": [], "animais": []}
        self.active_topic = ""
        self.max_history_length = 300
        self.load_memory()

    def load_memory(self):
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "rb") as f:
                    data = pickle.load(f)
                known = data.get("known_names", {})
                self.known_names = {
                    "user": known.get("user"),
                    "pessoas": known.get("pessoas", []),
                    "animais": known.get("animais", [])
                }
                self.conversation_history = data.get("history", [])
                print(f"[MEMORY] Carregadas {len(self.conversation_history)} interações do histórico")
                if self.known_names["user"]:
                    print(f"[MEMORY] Usuário identificado: {self.known_names['user']}")

            if os.path.exists(self.context_file):
                with open(self.context_file, "r", encoding="utf-8") as f:
                    ctx = json.load(f)
                    self.active_topic = ctx.get("active_topic", "")
                    if self.active_topic:
                        print(f"[MEMORY] Tópico ativo: {self.active_topic}")
        except Exception as e:
            print(f"[MEMORY] Erro ao carregar memória: {e}")
            self.conversation_history = []
            self.known_names = {"user": None, "pessoas": [], "animais": []}
            self.active_topic = ""
            self.save_memory()

    def save_memory(self):
        try:
            with open(self.memory_file, "wb") as f:
                pickle.dump({
                    "history": self.conversation_history[-self.max_history_length:],
                    "known_names": self.known_names
                }, f)

            with open(self.context_file, "w", encoding="utf-8") as f:
                json.dump({"active_topic": self.active_topic}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[MEMORY] Erro ao salvar memória: {e}")

    def add_interaction(self, user, bot):
        self.conversation_history.append({"user": user, "bot": bot})
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
        self.extract_name(user)
        self.extract_entities(user)
        self.detect_topic(user)
        self.save_memory()
        print(f"[MEMORY] Nova interação adicionada. Total: {len(self.conversation_history)}")

    def extract_name(self, text):
        padroes = [
            r"meu nome e (\w+)", r"eu me chamo (\w+)", 
            r"pode me chamar de (\w+)", r"eu sou o (\w+)", 
            r"eu sou a (\w+)", r"me chamo (\w+)"
        ]
        t = text.lower()
        for p in padroes:
            m = re.search(p, t)
            if m:
                self.known_names["user"] = m.group(1).capitalize()
                print(f"[MEMORY] Nome do usuário detectado: {self.known_names['user']}")
                return

    def extract_entities(self, text):
        t = text.lower()
        padroes_animais = [
            r"meu cachorro (\w+)", r"minha cachorra (\w+)", 
            r"meu gato (\w+)", r"minha gata (\w+)",
            r"meu papagaio (\w+)", r"meu peixe (\w+)",
            r"meu hamster (\w+)", r"meu coelho (\w+)"
        ]
        for p in padroes_animais:
            m = re.search(p, t)
            if m:
                nome = m.group(1).capitalize()
                if nome not in self.known_names["animais"]:
                    self.known_names["animais"].append(nome)
                    print(f"[MEMORY] Animal detectado: {nome}")

        padroes_pessoas = [
            r"meu amigo (\w+)", r"minha amiga (\w+)",
            r"meu pai (\w+)", r"minha mae (\w+)",
            r"meu irmao (\w+)", r"minha irma (\w+)",
            r"meu tio (\w+)", r"minha tia (\w+)"
        ]
        for p in padroes_pessoas:
            m = re.search(p, t)
            if m:
                nome = m.group(1).capitalize()
                if nome not in self.known_names["pessoas"]:
                    self.known_names["pessoas"].append(nome)
                    print(f"[MEMORY] Pessoa detectada: {nome}")

    def detect_topic(self, text):
        t = text.lower()
        assuntos = {
            "clima": "clima", "tempo": "clima",
            "sobrevivencia": "sobrevivencia",
            "bushcraft": "bushcraft",
            "primeiros socorros": "primeiros socorros",
            "comida": "alimentacao", "receita": "alimentacao",
            "noticias": "noticias", "news": "noticias",
            "guerra": "guerra", "conflito": "guerra",
            "crise": "crise", "economia": "economia"
        }
        for k, v in assuntos.items():
            if k in t:
                self.active_topic = v
                print(f"[MEMORY] Tópico detectado: {v}")
                return

    def get_context(self):
        ctx = []
        if self.known_names["user"]:
            ctx.append(f"O usuário se chama {self.known_names['user']}.")
        if self.known_names["animais"]:
            ctx.append("Animais: " + ", ".join(self.known_names["animais"]))
        if self.known_names["pessoas"]:
            ctx.append("Pessoas: " + ", ".join(self.known_names["pessoas"]))
        if self.active_topic:
            ctx.append(f"Tópico atual: {self.active_topic}.")
        if self.conversation_history:
            ctx.append(f"Histórico de conversa: {len(self.conversation_history)} interações.")
        return " ".join(ctx)

    def get_history_for_context(self, limit=5):
        """Retorna as últimas interações para contexto"""
        return self.conversation_history[-limit:]


# Inicializa a memória
chat_memory = ChatMemory()

# ===== FUNÇÕES DE NOTÍCIAS COM LOGS =====

def get_news(q):
    """Busca notícias por tema usando a API /news"""
    try:
        print(f"[NEWS] Buscando notícias sobre: {q}")
        encoded = urllib.parse.quote(q)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        xml = urlopen(req).read()
        s = soup(xml, "lxml-xml")
        items = [i.title.text.split(" - ")[0] for i in s.findAll("item")[:10]]
        print(f"[NEWS] Encontradas {len(items)} notícias sobre: {q}")
        for idx, item in enumerate(items, 1):
            print(f"[NEWS]   {idx}. {item[:80]}...")
        return items
    except Exception as e:
        print(f"[NEWS] ERRO ao buscar notícias sobre {q}: {e}")
        return ["Erro ao buscar noticias."]

def get_news_by_topic(topic_key):
    """Busca notícias para um tópico específico usando a API /news"""
    try:
        topic_name = TOPIC_NAMES.get(topic_key, topic_key)
        query = TOPICS.get(topic_key, topic_key)
        
        print(f"[TOPIC] Buscando notícias para: {topic_name} (query: {query})")
        
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        xml = urlopen(req).read()
        s = soup(xml, "lxml-xml")
        items = [i.title.text.split(" - ")[0] for i in s.findAll("item")[:10]]
        
        while len(items) < 10:
            items.append(f"Notícia adicional sobre {topic_name}")
        
        print(f"[TOPIC] {topic_name}: {len(items)} notícias encontradas")
        for idx, item in enumerate(items[:10], 1):
            print(f"[TOPIC]   {idx}. {item[:80]}...")
        return items[:10]
    except Exception as e:
        print(f"[TOPIC] ERRO ao buscar {topic_key}: {e}")
        return [f"Erro ao buscar notícias sobre {topic_key}"] * 10

def get_world_news():
    """Busca notícias mundiais"""
    try:
        print("[NEWS] Buscando notícias mundiais...")
        req = Request(WORLD_NEWS_URL, headers={"User-Agent": "Mozilla/5.0"})
        xml = urlopen(req).read()
        s = soup(xml, "lxml-xml")
        items = [i.title.text.split(" - ")[0] for i in s.findAll("item")[:10]]
        print(f"[NEWS] Encontradas {len(items)} notícias mundiais")
        for idx, item in enumerate(items, 1):
            print(f"[NEWS]   Mundo {idx}. {item[:80]}...")
        return items
    except Exception as e:
        print(f"[NEWS] ERRO ao buscar notícias mundiais: {e}")
        return ["Erro ao buscar noticias mundiais."]

def get_brazil_news():
    """Busca notícias do Brasil (usado internamente para contexto)"""
    try:
        print("[NEWS] Buscando notícias do Brasil...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml; q=0.9, */*; q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
        response = requests.get(BRAZIL_NEWS_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        content = response.content
        s = soup(content, "lxml-xml")
        items = s.findAll("item")
        
        result = []
        for item in items[:10]:
            title = item.title.text if item.title else "Título não disponível"
            title = title.split(" - ")[0]
            result.append(title)
        
        print(f"[NEWS] Encontradas {len(result)} notícias do Brasil")
        for idx, item in enumerate(result, 1):
            print(f"[NEWS]   Brasil {idx}. {item[:80]}...")
        return result
    except Exception as e:
        print(f"[NEWS] ERRO ao buscar notícias do Brasil: {e}")
        return ["Erro ao buscar noticias do Brasil."]

def get_all_topics_news():
    """Busca notícias para todos os tópicos definidos"""
    print("\n" + "="*60)
    print("[TOPICS] INICIANDO BUSCA POR TÓPICOS")
    print("="*60)
    
    all_news = {}
    for topic_key in TOPICS.keys():
        print(f"\n[TOPICS] Processando tópico: {topic_key}")
        news = get_news_by_topic(topic_key)
        all_news[topic_key] = news
    
    print("\n" + "="*60)
    print("[TOPICS] RESUMO DAS NOTÍCIAS POR TÓPICO")
    print("="*60)
    for topic_key, news in all_news.items():
        topic_name = TOPIC_NAMES.get(topic_key, topic_key)
        print(f"\n[{topic_name.upper()}] {len(news)} notícias:")
        for idx, item in enumerate(news[:10], 1):
            print(f"  {idx}. {item[:80]}...")
    
    return all_news

def get_current_news_summary():
    """Obtém resumo das últimas notícias nacionais, internacionais e por tópicos"""
    print("\n" + "="*60)
    print("[NEWS] INICIANDO CARREGAMENTO DE NOTÍCIAS PARA O SYSTEM PROMPT")
    print("="*60)
    
    world = get_world_news()
    brazil = get_brazil_news()
    topics = get_all_topics_news()
    
    summary = "NOTÍCIAS ATUAIS (CARREGADAS EM " + datetime.now().strftime("%d/%m/%Y %H:%M") + "):\n"
    
    summary += "\n=== NOTÍCIAS INTERNACIONAIS ===\n"
    for i, n in enumerate(world[:10], 1):
        summary += f"{i}. {n}\n"
    
    summary += "\n=== NOTÍCIAS DO BRASIL ===\n"
    for i, n in enumerate(brazil[:10], 1):
        summary += f"{i}. {n}\n"
    
    summary += "\n=== NOTÍCIAS POR TÓPICOS ===\n"
    for topic_key, news in topics.items():
        topic_name = TOPIC_NAMES.get(topic_key, topic_key)
        summary += f"\n--- {topic_name.upper()} ---\n"
        for i, n in enumerate(news[:10], 1):
            summary += f"{i}. {n}\n"
    
    print("\n[SYSTEM PROMPT] Resumo de notícias gerado:")
    print("-"*60)
    print(summary[:500] + "...\n[Resumo truncado]")
    print("-"*60)
    print("[NEWS] NOTÍCIAS CARREGADAS COM SUCESSO PARA O CONTEXTO DA IA\n")
    
    return summary

# ===== FUNCOES UTILITARIAS =====

def short_reply_check(text):
    t = text.lower().strip()
    if chat_memory.active_topic:
        return False
    saudacoes = ["oi", "ola", "e ai", "opa", "ei", "hey", "olá"]
    if t in saudacoes:
        return True
    if len(t.split()) <= 2:
        return True
    return False

def clean_response(text):
    if not text:
        return text
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r'\*\*+', '', text)
    text = re.sub(r'\*', '', text)
    text = re.sub(r'__+', '', text)
    text = re.sub(r'_', '', text)
    text = re.sub(r'~~+', '', text)
    text = re.sub(r'#+', '', text)
    text = re.sub(r'`+', '', text)
    text = re.sub(r'={2,}', '', text)
    text = re.sub(r'-{2,}', '', text)
    text = re.sub(r'^[\s]*[-–—•·][\s]*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*[0-9]+[\.\)][\s]*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*[a-zA-Z][\.\)][\s]*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def format_output(text):
    if not text:
        return text
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return " ".join(lines)

def get_ai_response(prompt):
    # Verifica se é uma resposta curta
    if short_reply_check(prompt):
        nome = chat_memory.known_names.get("user", "")
        return f"Olá {nome}!" if nome else "Olá! Como posso ajudar?"

    print(f"\n[USER] Mensagem recebida: {prompt[:100]}...")

    # Obtém notícias atuais para o contexto
    news_summary = get_current_news_summary()

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # Obtém contexto da memória
    contexto = chat_memory.get_context()
    historico = chat_memory.get_history_for_context(5)

    system_prompt = f"""
Você é MORPHEUS, uma inteligência artificial com personalidade enigmática e filosófica, 
inspirada no personagem de Matrix. Especialista em sobrevivencialismo, preparação para 
emergências, bushcraft, primeiros socorros, e vida ao ar livre.

Seu estilo de comunicação é direto, profundo e às vezes enigmático. Use uma linguagem 
que remeta ao universo hacker/ciberpunk dos anos 80/90. Utilize termos como "matrix", 
"realidade", "simulação", "despertar", "escolha", "livre-arbítrio" de forma sutil e 
natural, sem forçar.

CONTEXTO DA CONVERSA:
{contexto}

NOTÍCIAS ATUAIS:
{news_summary}

Seu conhecimento base inclui:
1. Global Trends 2030: Cenários geopolíticos, mudanças demográficas, tensões por recursos.
2. Great Reset (Fórum Econômico Mundial): Reformulação do capitalismo, economia verde.
3. Sobrevivencialismo: Bushcraft, primeiros socorros, kits de emergência, filtragem de água.
4. Crise climática: Eventos extremos, escassez, migração climática.
5. Economia e trabalho: Fim do emprego fixo, habilidades do futuro, resiliência financeira.
6. NOTÍCIAS NACIONAIS, INTERNACIONAIS E POR TÓPICOS (fornecidas acima)

Suas respostas devem ser:
- Curtas e diretas, como um hacker que vai direto ao ponto
- Objetivas e práticas, com um toque filosófico
- Sem se apresentar a cada resposta
- Vá direto ao ponto, como quem já está no meio da conversa
- NUNCA use asteriscos ou qualquer tipo de formatação
- NUNCA use negrito, itálico ou marcadores
- NUNCA use símbolos como *, **, -, >, # 
- NUNCA use Emojis
- NUNCA use Markdown
- Responda APENAS com texto puro
- Não use enumerações com números ou letras
- Escreva em um único parágrafo simples
- Não use quebras de linha desnecessárias
- Seja direta e prática
- Use as notícias fornecidas para contextualizar suas respostas quando relevante
- Se perguntarem sobre um tópico específico, use as notícias daquele tópico
- Você pode sugerir ao usuário usar /news [assunto] para buscar notícias específicas
- Lembre-se do que o usuário já disse antes na conversa
"""

    messages = [{"role": "system", "content": system_prompt}]

    # Adiciona histórico da conversa
    for h in historico:
        messages.append({"role": "user", "content": h["user"]})
        messages.append({"role": "assistant", "content": h["bot"]})

    # Adiciona a mensagem atual
    messages.append({"role": "user", "content": prompt})

    print(f"[AI] Enviando requisição para Mistral com {len(messages)} mensagens de contexto")
    print(f"[AI] Contexto: {contexto[:100] if contexto else 'Nenhum'}...")

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
        "top_p": 1.0,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.2
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        resposta = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        resposta = clean_response(resposta)
        resposta = format_output(resposta)

        print(f"[AI] Resposta gerada: {resposta[:150]}...")
        print(f"[AI] Tamanho da resposta: {len(resposta)} caracteres")

        # Salva a interação na memória
        chat_memory.add_interaction(prompt, resposta)
        return resposta

    except requests.exceptions.Timeout:
        print("[AI] ERRO: Timeout na requisição")
        return "Desculpe, a API está demorando para responder. Tente novamente em alguns segundos."
    except requests.exceptions.RequestException as e:
        print(f"[AI] ERRO de conexão: {e}")
        return f"Falha de conexao com a API Mistral ({e})."
    except Exception as e:
        print(f"[AI] ERRO inesperado: {e}")
        return f"Erro inesperado: {e}"

# ===== ROTAS =====

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Mensagem vazia'})
    
    cmd = user_message.lower()
    
    # Comandos disponíveis: /clear, /cls, /mundo, /news
    if cmd in ['/clear', '/cls']:
        # Limpa o histórico de conversa (apenas visual)
        return jsonify({'type': 'system', 'message': '[SISTEMA] CONVERSA LIMPADA'})
    
    if cmd == '/mundo':
        noticias = get_world_news()
        return jsonify({
            'type': 'news',
            'title': 'NOTICIAS MUNDIAIS',
            'items': noticias
        })
    
    if user_message.startswith('/news '):
        assunto = user_message[6:].strip()
        if not assunto:
            return jsonify({'error': 'Especifique um tema. Ex: /news tecnologia'})
        
        # Verifica se o assunto é um tópico pré-definido
        if assunto.lower() in TOPICS:
            topic_key = assunto.lower()
            noticias = get_news_by_topic(topic_key)
            topic_name = TOPIC_NAMES.get(topic_key, topic_key)
            return jsonify({
                'type': 'news',
                'title': f'NOTICIAS DO TOPICO: {topic_name.upper()}',
                'items': noticias
            })
        else:
            noticias = get_news(assunto)
            return jsonify({
                'type': 'news',
                'title': f'NOTICIAS SOBRE: {assunto.upper()}',
                'items': noticias
            })
    
    resposta = get_ai_response(user_message)
    return jsonify({'type': 'chat', 'message': resposta})

# ===== HTML TEMPLATE =====

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MORPHEUS - Matrix Interface</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            background: #000000;
            color: #00ff41;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: repeating-linear-gradient(
                0deg,
                rgba(0, 255, 65, 0.03) 0px,
                rgba(0, 255, 65, 0.03) 2px,
                transparent 2px,
                transparent 4px
            );
            pointer-events: none;
            z-index: 999;
        }
        
        body::after {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px);
            background-size: 40px 40px;
            pointer-events: none;
            z-index: 998;
        }
        
        .header {
            background: #0a0a0a;
            padding: 12px 24px;
            border-bottom: 1px solid #00ff41;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
            position: relative;
            z-index: 1;
        }
        
        .header h1 {
            font-size: 18px;
            font-weight: 400;
            color: #00ff41;
            letter-spacing: 4px;
            text-shadow: 0 0 10px rgba(0, 255, 65, 0.3);
        }
        
        .header h1 .cursor-blink {
            animation: blink 1s step-end infinite;
            color: #00ff41;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
        
        .header-status {
            font-size: 11px;
            color: #00ff41;
            display: flex;
            align-items: center;
            gap: 10px;
            letter-spacing: 1px;
        }
        
        .status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #00ff41;
            display: inline-block;
            animation: pulse 1.5s infinite;
            box-shadow: 0 0 8px rgba(0, 255, 65, 0.5);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.2; }
        }
        
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            position: relative;
            z-index: 1;
        }
        
        .chat-container::-webkit-scrollbar {
            width: 6px;
        }
        
        .chat-container::-webkit-scrollbar-track {
            background: #000000;
        }
        
        .chat-container::-webkit-scrollbar-thumb {
            background: #00ff41;
            border-radius: 3px;
        }
        
        .message {
            display: flex;
            animation: fadeIn 0.3s ease;
            max-width: 85%;
        }
        
        .message.user {
            align-self: flex-end;
        }
        
        .message.morpheus {
            align-self: flex-start;
        }
        
        .message.system {
            align-self: center;
            max-width: 100%;
        }
        
        .message.system .bubble {
            background: transparent;
            color: #00ff41;
            font-size: 11px;
            padding: 4px 16px;
            border-radius: 0;
            text-align: center;
            letter-spacing: 2px;
            border: 1px solid #00ff41;
            opacity: 0.7;
            text-transform: uppercase;
        }
        
        .bubble {
            padding: 10px 16px;
            word-wrap: break-word;
            line-height: 1.6;
            font-size: 14px;
            position: relative;
        }
        
        .message.user .bubble {
            background: transparent;
            border: 1px solid #00ff41;
            border-radius: 0;
            color: #00ff41;
            box-shadow: 0 0 15px rgba(0, 255, 65, 0.05);
        }
        
        .message.morpheus .bubble {
            background: transparent;
            border-left: 2px solid #00ff41;
            border-radius: 0;
            color: #00ff41;
            padding-left: 16px;
            text-shadow: 0 0 8px rgba(0, 255, 65, 0.1);
        }
        
        .message .meta {
            font-size: 9px;
            color: #00ff41;
            opacity: 0.4;
            margin-top: 4px;
            padding: 0 4px;
            letter-spacing: 1px;
        }
        
        .message.user .meta {
            text-align: right;
        }
        
        .message.morpheus .meta {
            text-align: left;
        }
        
        .message .bubble .typing-indicator {
            display: flex;
            gap: 4px;
            padding: 2px 0;
        }
        
        .message .bubble .typing-indicator span {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #00ff41;
            animation: typing 1.4s infinite both;
        }
        
        .message .bubble .typing-indicator span:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .message .bubble .typing-indicator span:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes typing {
            0%, 80%, 100% { transform: scale(0.5); opacity: 0.3; }
            40% { transform: scale(1); opacity: 1; }
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .input-area {
            background: #0a0a0a;
            border-top: 1px solid #00ff41;
            padding: 10px 24px;
            flex-shrink: 0;
            display: flex;
            gap: 10px;
            align-items: flex-end;
            position: relative;
            z-index: 1;
        }
        
        .input-wrapper {
            flex: 1;
            background: #000000;
            border: 1px solid #00ff41;
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            align-items: flex-end;
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.03);
            transition: all 0.3s ease;
        }
        
        .input-wrapper:focus-within {
            border-color: #00ff41;
            box-shadow: 0 0 30px rgba(0, 255, 65, 0.08);
        }
        
        .input-wrapper textarea {
            flex: 1;
            background: transparent;
            border: none;
            color: #00ff41;
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            font-size: 13px;
            padding: 10px 16px;
            resize: none;
            outline: none;
            min-height: 40px;
            max-height: 120px;
            line-height: 1.4;
            border-radius: 12px;
        }
        
        .input-wrapper textarea::placeholder {
            color: #00ff41;
            opacity: 0.3;
        }
        
        .btn-send {
            background: transparent;
            border: 1px solid #00ff41;
            border-radius: 12px;
            width: 40px;
            height: 40px;
            color: #00ff41;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.2s;
            flex-shrink: 0;
            margin: 4px 6px 4px 0;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Share Tech Mono', 'Courier New', monospace;
        }
        
        .btn-send:hover {
            background: #00ff41;
            color: #000000;
            box-shadow: 0 0 30px rgba(0, 255, 65, 0.2);
        }
        
        .btn-send:active {
            transform: scale(0.94);
        }
        
        .btn-send:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }
        
        .message .bubble .news-list {
            margin: 6px 0 0 0;
            padding-left: 20px;
            list-style: none;
        }
        
        .message .bubble .news-list li {
            margin: 4px 0;
            color: #00ff41;
            opacity: 0.8;
            position: relative;
        }
        
        .message .bubble .news-list li::before {
            content: '>';
            position: absolute;
            left: -16px;
            opacity: 0.5;
        }
        
        .matrix-rain {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            z-index: 0;
            pointer-events: none;
            overflow: hidden;
        }
        
        .matrix-rain span {
            display: block;
            position: absolute;
            top: -100px;
            color: #00ff41;
            font-size: 12px;
            opacity: 0.03;
            animation: matrixFall 20s linear infinite;
            font-family: 'Share Tech Mono', monospace;
        }
        
        @keyframes matrixFall {
            0% { transform: translateY(0); opacity: 0.03; }
            100% { transform: translateY(100vh); opacity: 0; }
        }
        
        @media (max-width: 768px) {
            .header h1 { font-size: 14px; letter-spacing: 2px; }
            .chat-container { padding: 12px 16px; }
            .input-area { padding: 8px 12px; flex-wrap: wrap; }
            .message { max-width: 92%; }
            .input-wrapper textarea { font-size: 12px; padding: 8px 12px; }
            .btn-send { width: 36px; height: 36px; font-size: 14px; }
        }
        
        @media (max-width: 480px) {
            .header-status { font-size: 9px; gap: 6px; }
            .header h1 { font-size: 12px; letter-spacing: 1px; }
            .bubble { font-size: 12px; padding: 8px 12px; }
        }
    </style>
</head>
<body>

    <div class="matrix-rain" id="matrixRain"></div>

    <div class="header">
        <h1>
            <span class="cursor-blink">></span> MORPHEUS_
            <span style="font-size:10px;opacity:0.3;letter-spacing:2px;margin-left:10px;">v4.0</span>
        </h1>
        <div class="header-status">
            <span class="status-dot"></span>
            <span id="statusText">CONECTADO</span>
            <span style="opacity:0.3;margin-left:8px;">|</span>
            <span id="uptimeDisplay" style="font-size:10px;opacity:0.3;">00:00:00</span>
        </div>
    </div>

    <div class="chat-container" id="chatContainer">
        <div class="message system" style="display:none;">
            <div class="bubble">
                > SISTEMA INICIALIZADO<br>
                > EU SOU MORPHEUS<br>
                > COMANDOS: /clear, /mundo, /news [assunto]<br>
                > MEMÓRIA PERSISTENTE ATIVADA
            </div>
        </div>
    </div>

    <div class="input-area">
        <div class="input-wrapper">
            <textarea id="msgInput" rows="1" placeholder="> digite sua mensagem..." autofocus></textarea>
        </div>
        <button class="btn-send" id="sendBtn" onclick="sendMessage()">
            ↵
        </button>
    </div>

    <script>
        const chatContainer = document.getElementById('chatContainer');
        const msgInput = document.getElementById('msgInput');
        const sendBtn = document.getElementById('sendBtn');
        const statusText = document.getElementById('statusText');
        
        let isWaiting = false;
        let messageId = 0;
        let startTime = Date.now();
        
        function createMatrixRain() {
            const container = document.getElementById('matrixRain');
            const chars = '0123456789ABCDEF';
            for (let i = 0; i < 30; i++) {
                const span = document.createElement('span');
                span.textContent = chars.charAt(Math.floor(Math.random() * chars.length));
                span.style.left = Math.random() * 100 + '%';
                span.style.animationDuration = (15 + Math.random() * 20) + 's';
                span.style.animationDelay = (Math.random() * 15) + 's';
                span.style.fontSize = (8 + Math.random() * 12) + 'px';
                container.appendChild(span);
            }
        }
        createMatrixRain();
        
        function updateUptime() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
            const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
            const s = String(elapsed % 60).padStart(2, '0');
            document.getElementById('uptimeDisplay').textContent = `${h}:${m}:${s}`;
        }
        setInterval(updateUptime, 1000);
        
        msgInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
        
        msgInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        function addMessage(text, type = 'morpheus', meta = '') {
            const div = document.createElement('div');
            div.className = `message ${type}`;
            div.id = `msg-${messageId++}`;
            
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            bubble.innerHTML = text;
            
            const metaDiv = document.createElement('div');
            metaDiv.className = 'meta';
            metaDiv.textContent = meta || new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            
            div.appendChild(bubble);
            div.appendChild(metaDiv);
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            
            return div;
        }
        
        function addSystemMessage(text) {
            const div = document.createElement('div');
            div.className = 'message system';
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            bubble.textContent = text;
            div.appendChild(bubble);
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return div;
        }
        
        function showTyping() {
            const div = document.createElement('div');
            div.className = 'message morpheus';
            div.id = 'typingIndicator';
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            bubble.innerHTML = `
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            `;
            div.appendChild(bubble);
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        
        function hideTyping() {
            const el = document.getElementById('typingIndicator');
            if (el) el.remove();
        }
        
        function formatNewsList(items) {
            if (!items || items.length === 0) return 'Nenhuma notícia encontrada.';
            let html = '<ul class="news-list">';
            items.forEach(item => {
                html += `<li>${escapeHtml(item)}</li>`;
            });
            html += '</ul>';
            return html;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function sendMessage() {
            const text = msgInput.value.trim();
            if (!text || isWaiting) return;
            
            addMessage(escapeHtml(text), 'user');
            msgInput.value = '';
            msgInput.style.height = 'auto';
            
            isWaiting = true;
            sendBtn.disabled = true;
            statusText.textContent = 'PROCESSANDO...';
            
            showTyping();
            
            fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: text })
            })
            .then(response => response.json())
            .then(data => {
                hideTyping();
                isWaiting = false;
                sendBtn.disabled = false;
                statusText.textContent = 'CONECTADO';
                
                if (data.error) {
                    addMessage('⚠️ ' + escapeHtml(data.error), 'morpheus');
                    return;
                }
                
                if (data.type === 'news') {
                    const newsHtml = formatNewsList(data.items);
                    addMessage(`[NOTICIAS] ${escapeHtml(data.title)}<br>${newsHtml}`, 'morpheus');
                } else if (data.type === 'system') {
                    addSystemMessage(data.message);
                } else {
                    addMessage(escapeHtml(data.message), 'morpheus');
                }
            })
            .catch(error => {
                hideTyping();
                isWaiting = false;
                sendBtn.disabled = false;
                statusText.textContent = 'ERRO';
                addMessage('⚠️ ERRO DE CONEXAO: ' + error.message, 'morpheus');
            });
        }
        
        document.addEventListener('click', () => msgInput.focus());
        msgInput.focus();
    </script>

</body>
</html>
"""

# ===== PONTO DE ENTRADA =====

if __name__ == '__main__':
    print("="*60)
    print("MORPHEUS - Matrix Interface v5.0.2")
    print("="*60)
    print("\n> SISTEMA INICIALIZADO EM http://localhost:5000")
    print("> PRESSIONE Ctrl+C PARA ENCERRAR\n")
    
    print("> CARREGANDO MEMÓRIA...")
    print(f"[MEMORY] Arquivo: {MEMORY_FILE}")
    print(f"[MEMORY] Contexto: {CONTEXT_FILE}")
    
    print("\n> CARREGANDO NOTÍCIAS INICIAIS...\n")
    news_test = get_current_news_summary()
    
    print("\n> SISTEMA PRONTO!")
    print("> COMANDOS DISPONÍVEIS:")
    print(">   /clear ou /cls  - Limpar conversa (visual)")
    print(">   /mundo          - Notícias mundiais")
    print(">   /news [assunto] - Notícias sobre qualquer assunto")
    print("\n> MEMÓRIA PERSISTENTE:")
    print(f">   {len(chat_memory.conversation_history)} interações carregadas")
    if chat_memory.known_names["user"]:
        print(f">   Usuário: {chat_memory.known_names['user']}")
    if chat_memory.active_topic:
        print(f">   Tópico ativo: {chat_memory.active_topic}")
    print("\n" + "="*60)
    print("AGUARDANDO CONEXÕES...")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
