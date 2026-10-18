# Como Publicar seu App na Nuvem Grátis (Sem VPS)

O seu app já está com o **Supabase Storage** conectado (bucket `tiktok-videos`), o que significa que todos os vídeos ficam salvos na nuvem com link público automático!

Para colocar o painel online 24 horas por dia (para você acessar do celular ou de qualquer lugar, mesmo com o PC desligado):

---

### Passo 1: Subir o projeto para o seu GitHub (2 minutos)
1. Crie um repositório no seu [GitHub](https://github.com/new) (pode ser Privado). Ex: `tiktok-buffer-automator`.
2. Na pasta do projeto:
   `C:\Users\leurickkkk77\.gemini\antigravity\scratch\tiktok-buffer-automator`
3. Abra o terminal e envie os arquivos para o seu GitHub:
   ```bash
   git init
   git add .
   git commit -m "TikTok Buffer Automator com Supabase"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
   git push -u origin main
   ```

---

### Passo 2: Publicar no Render.com (100% Gratuito)
1. Crie uma conta gratuita em [Render.com](https://render.com).
2. Clique no botão azul **"New +"** no topo e escolha **"Web Service"**.
3. Conecte sua conta do GitHub e selecione o repositório `tiktok-buffer-automator`.
4. Preencha apenas o básico:
   - **Name:** `tiktok-buffer-automator` (ou o nome que quiser)
   - **Region:** Ohio (US East) ou Oregon
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free` ($0/mês)
5. Clique em **"Deploy Web Service"**!
6. Em cerca de 2 minutos, o Render vai gerar o seu link oficial:
   👉 **`https://seu-app.onrender.com`**

---

### Passo 3: Deixar o Robô Ativo 24h sem dormir (O Truque Gratuito)
No plano gratuito do Render, o app entra em modo de espera após 15 minutos sem visitas. Para deixá-lo **sempre acordado postando sozinho**:

1. Acesse o site gratuito: [cron-job.org](https://cron-job.org).
2. Crie um cron para chamar a URL:
   `https://seu-app.onrender.com/api/sync`
   - Intervalo: **A cada 10 minutos**.
3. **Pronto!**
   - O cron-job acorda seu app a cada 10 minutos.
   - O endpoint `/api/sync` confere a fila do Buffer e abastece com os novos vídeos do Supabase automaticamente!
