import sys
import os

# Adiciona o diretório raiz ao sys.path para importação correta no Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
