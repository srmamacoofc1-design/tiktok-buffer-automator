# TikTok Buffer Automator Pro

Sistema completo de automação contínua para postagens no TikTok através da API do Buffer, com suporte a **múltiplas contas/tokens**, **estoque infinito de vídeos** e **alimentação inteligente da fila (Auto-Feeder)**.

---

## 🚀 Como Iniciar o App

1. Abra a pasta do projeto:
   `C:\Users\leurickkkk77\.gemini\antigravity\scratch\tiktok-buffer-automator`
2. Dê um duplo-clique no arquivo:
   👉 **`iniciar.bat`**
3. O painel abrirá automaticamente no seu navegador em:
   👉 **`http://localhost:8000`**

---

## 📋 Recursos Principais

1. **Multi-Contas & Multi-Perfis:**
   - Suporte a ilimitadas chaves de API do Buffer.
   - Cada conta do Buffer (plano gratuito) suporta até 3 perfis.
   - Os seus 3 perfis já estão conectados e configurados:
     - `@leurickshop`
     - `@leurick_o_meno`
     - `@erickmania5`

2. **Estoque Infinito de Vídeos:**
   - O Buffer Grátis limita a fila em **10 posts simultâneos**.
   - O nosso app permite que você suba **30, 50, 100 vídeos** de uma só vez para o estoque local.
   - O **Robô Auto-Feeder** monitora a fila a cada 5 minutos: sempre que um vídeo for publicado no TikTok e liberar espaço na fila, ele pega o próximo vídeo do estoque e agenda no Buffer automaticamente!

3. **Automação Completa de I.A e Legendas:**
   - Declaração de conteúdo por I.A ativada por padrão (`isAiGenerated: true`).
   - Títulos gerados e limpos automaticamente a partir dos nomes dos arquivos.
   - Hashtags adicionadas automaticamente.
   - Previsão em tempo real de quantos dias de postagens o estoque vai render.
