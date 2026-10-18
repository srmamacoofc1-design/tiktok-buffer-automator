import urllib.request
import json
import os
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

BUFFER_API_URL = "https://api.buffer.com"

class BufferClient:
    def __init__(self, token: str):
        self.token = token.strip()
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None, retries: int = 5) -> Dict[str, Any]:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(BUFFER_API_URL, data=data_bytes, headers=self.headers)
        
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    if "errors" in res:
                        raise Exception(f"Buffer GraphQL Error: {json.dumps(res['errors'])}")
                    return res.get("data", {})
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries - 1:
                    wait_time = (attempt + 1) * 10
                    print(f"    [Buffer Rate Limit 429] Aguardando {wait_time}s antes de tentar novamente...")
                    import time
                    time.sleep(wait_time)
                else:
                    raise e

    def get_account_and_channels(self) -> Dict[str, Any]:
        """Recupera informações da conta e lista todos os canais conectados"""
        query = """
        query {
          account {
            id
            email
            organizations {
              id
              name
            }
          }
        }
        """
        data = self.execute_query(query)
        account = data.get("account", {})
        orgs = account.get("organizations", [])
        
        all_channels = []
        for org in orgs:
            org_id = org["id"]
            c_query = f"""
            query {{
              channels(input: {{ organizationId: "{org_id}" }}) {{
                id
                name
                service
              }}
            }}
            """
            c_data = self.execute_query(c_query)
            channels = c_data.get("channels", [])
            for ch in channels:
                ch["organization_id"] = org_id
                all_channels.append(ch)
                
        return {
            "account": account,
            "channels": all_channels
        }

    def get_scheduled_posts(self, org_id: str, channel_id: str) -> List[Dict[str, Any]]:
        """Busca posts que estão atualmente agendados na fila do Buffer para o canal"""
        query = """
        query GetPendingPosts($orgId: OrganizationId!, $channelId: ChannelId!) {
          posts(first: 50, input: {
            organizationId: $orgId,
            filter: { status: [scheduled], channelIds: [$channelId] }
          }) {
            edges {
              node {
                id
                text
                dueAt
                status
              }
            }
          }
        }
        """
        data = self.execute_query(query, {"orgId": org_id, "channelId": channel_id})
        edges = data.get("posts", {}).get("edges", [])
        return [e["node"] for e in edges]

    def create_tiktok_post(
        self,
        channel_id: str,
        text: str,
        video_url: str,
        due_at_iso: str,
        is_ai_generated: bool = True
    ) -> Dict[str, Any]:
        """Agenda um post de vídeo no TikTok com metadata de IA declarada"""
        mutation = """
        mutation CreateTikTokPost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess {
              post {
                id
                text
                dueAt
                status
              }
            }
            ... on MutationError {
              message
            }
          }
        }
        """
        variables = {
            "input": {
                "channelId": channel_id,
                "text": text,
                "schedulingType": "automatic",
                "mode": "customScheduled",
                "dueAt": due_at_iso,
                "needsApproval": False,
                "assets": [
                    {
                        "video": {
                            "url": video_url,
                            "metadata": {
                                "thumbnailOffset": 1000
                            }
                        }
                    }
                ],
                "metadata": {
                    "tiktok": {
                        "isAiGenerated": is_ai_generated
                    }
                }
            }
        }
        res = self.execute_query(mutation, variables)
        create_res = res.get("createPost", {})
        if "message" in create_res:
            raise Exception(f"Erro ao criar post no Buffer: {create_res['message']}")
        return create_res.get("post", {})

    def get_channel_metrics(self, org_id: str, channel_id: str) -> Dict[str, Any]:
        """Busca os posts recentes enviados e calcula métricas acumuladas (views, curtidas, alcance)"""
        query = """
        query GetSentMetrics($orgId: OrganizationId!, $channelId: ChannelId!) {
          posts(first: 30, input: {
            organizationId: $orgId,
            filter: { status: [sent], channelIds: [$channelId] }
          }) {
            edges {
              node {
                id
                text
                sentAt
                metrics {
                  name
                  value
                }
              }
            }
          }
        }
        """
        try:
            data = self.execute_query(query, {"orgId": org_id, "channelId": channel_id})
            edges = data.get("posts", {}).get("edges", [])
            
            total_views = 0
            total_likes = 0
            total_comments = 0
            total_shares = 0
            total_reach = 0
            recent_posts = []

            for e in edges:
                node = e.get("node", {})
                p_metrics = {m["name"]: m["value"] for m in node.get("metrics", [])}
                v_views = p_metrics.get("Video Views", 0)
                v_likes = p_metrics.get("Reactions", 0)
                v_comms = p_metrics.get("Comments", 0)
                v_shares = p_metrics.get("Shares", 0)
                v_reach = p_metrics.get("Reach", 0)

                total_views += v_views
                total_likes += v_likes
                total_comments += v_comms
                total_shares += v_shares
                total_reach += v_reach

                recent_posts.append({
                    "id": node.get("id"),
                    "title": (node.get("text") or "")[:40],
                    "sent_at": node.get("sentAt"),
                    "views": int(v_views),
                    "likes": int(v_likes),
                    "comments": int(v_comms),
                    "shares": int(v_shares)
                })

            return {
                "posts_analyzed": len(edges),
                "total_views": int(total_views),
                "total_likes": int(total_likes),
                "total_comments": int(total_comments),
                "total_shares": int(total_shares),
                "total_reach": int(total_reach),
                "recent_posts": recent_posts[:8]
            }
        except Exception as e:
            return {
                "error": str(e),
                "posts_analyzed": 0,
                "total_views": 0,
                "total_likes": 0,
                "total_comments": 0,
                "total_shares": 0,
                "total_reach": 0,
                "recent_posts": []
            }

    def get_profile_schedule_and_history(self, org_id: str, channel_id: str) -> Dict[str, Any]:
        """Busca os posts agendados na fila (que faltam) e os posts já enviados (já postados) com horários e miniaturas"""
        query = """
        query GetQueueAndHistory($orgId: OrganizationId!, $channelId: ChannelId!) {
          scheduled: posts(first: 20, input: {
            organizationId: $orgId,
            filter: { status: [scheduled], channelIds: [$channelId] }
          }) {
            edges {
              node {
                id
                text
                dueAt
                status
                assets {
                  ... on VideoAsset {
                    thumbnail
                    source
                  }
                }
              }
            }
          }
          sent: posts(first: 20, input: {
            organizationId: $orgId,
            filter: { status: [sent], channelIds: [$channelId] }
          }) {
            edges {
              node {
                id
                text
                sentAt
                status
                externalLink
                assets {
                  ... on VideoAsset {
                    thumbnail
                    source
                  }
                }
              }
            }
          }
        }
        """
        data = self.execute_query(query, {"orgId": org_id, "channelId": channel_id})
        
        def _extract_items(edges, is_sent=False):
            items = []
            for e in edges:
                node = e.get("node", {})
                assets = node.get("assets", [])
                thumb = None
                video_url = None
                if assets and isinstance(assets, list):
                    for a in assets:
                        if isinstance(a, dict):
                            thumb = a.get("thumbnail") or thumb
                            video_url = a.get("source") or video_url
                            
                item = {
                    "id": node.get("id"),
                    "title": (node.get("text") or "").strip().split("\n")[0][:80] or "Vídeo TikTok",
                    "full_text": (node.get("text") or "").strip(),
                    "status": node.get("status"),
                    "thumbnail": thumb,
                    "video_url": video_url
                }
                if is_sent:
                    item["sent_at"] = node.get("sentAt")
                    item["external_link"] = node.get("externalLink")
                else:
                    item["due_at"] = node.get("dueAt")
                items.append(item)
            return items

        scheduled_edges = data.get("scheduled", {}).get("edges", [])
        sent_edges = data.get("sent", {}).get("edges", [])

        scheduled_items = _extract_items(scheduled_edges, is_sent=False)
        sent_items = _extract_items(sent_edges, is_sent=True)

        scheduled_items.sort(key=lambda x: x.get("due_at") or "")
        sent_items.sort(key=lambda x: x.get("sent_at") or "", reverse=True)

        return {
            "scheduled": scheduled_items,
            "sent": sent_items,
            "scheduled_count": len(scheduled_items),
            "sent_count": len(sent_items)
        }



SUPABASE_URL = "https://zjrvsqpfmhazcxqjwlei.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpqcnZzcXBmbWhhemN4cWp3bGVpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NDQxNTI4MywiZXhwIjoyMDk5OTkxMjgzfQ.XWFS053v8PmxpdJSMXY-T8GR0RiojCYvZZJnrepCRM4"

def upload_video_to_public_url(local_path: str) -> str:
    """
    Faz upload do arquivo MP4 para o bucket 'tiktok-videos' no Supabase Storage do usuário,
    gerando a URL pública direta permanente para o Buffer postar no TikTok.
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {local_path}")

    filename = os.path.basename(local_path)
    import unicodedata, re
    nfkd = unicodedata.normalize('NFKD', filename)
    ascii_str = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    clean_base = re.sub(r'[^a-zA-Z0-9_\.]', '_', ascii_str)
    clean_filename = f"{int(datetime.now().timestamp())}_{clean_base}"


    # 1. Tentar túnel Cloudflare local se cloudflared.exe estiver presente
    try:
        from tunnel_manager import CloudflareTunnel
        tunnel = CloudflareTunnel.get_instance()
        tunnel_url = tunnel.get_public_url_for_file(local_path)
        if tunnel_url and tunnel_url.startswith("http"):
            return tunnel_url
    except Exception as e:
        print(f"Aviso: Túnel Cloudflare indisponível ({e}), tentando Supabase...")

    # 2. Tentar upload direto no Supabase Storage do usuário
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        with open(local_path, "rb") as f:
            file_bytes = f.read()
            supabase.storage.from_("tiktok-videos").upload(
                path=clean_filename,
                file=file_bytes,
                file_options={"content-type": "video/mp4", "upsert": "true"}
            )
        pub_url = supabase.storage.from_("tiktok-videos").get_public_url(clean_filename)
        if pub_url and pub_url.startswith("http"):
            return pub_url
    except Exception as e:
        print(f"Aviso: Upload no Supabase falhou ({e}), tentando fallback...")

    # 2. Fallback de alta disponibilidade
    url = "https://litterbox.catbox.moe/resources/internals/api.php"
    with open(local_path, "rb") as f:
        response = requests.post(
            url,
            data={"reqtype": "fileupload", "time": "72h"},
            files={"fileToUpload": (filename, f, "video/mp4")},
            timeout=180
        )
        
    if response.status_code == 200 and response.text.startswith("http"):
        return response.text.strip()
    else:
        raise Exception(f"Falha ao gerar link público do vídeo: {response.status_code} - {response.text}")

