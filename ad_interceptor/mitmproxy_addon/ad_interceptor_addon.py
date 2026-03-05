from mitmproxy import http
import psycopg2, json, os
from datetime import datetime

AD_DOMAINS = [
    "googleads.g.doubleclick.net",
    "pagead2.googlesyndication.com",
    "auction.unityads.unity3d.com",
    "ms.applovin.com",
    "outcome-ssp.supersonic.com"
]

PG_CONN = None

def get_pg_conn():
    global PG_CONN
    if PG_CONN is None or PG_CONN.closed:
        PG_CONN = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "eddie-postgres"),
            port=os.getenv("POSTGRES_PORT", "5433"),
            dbname=os.getenv("POSTGRES_DB", "btc_trading"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "eddie_memory_2026")
        )
        PG_CONN.autocommit = True
    return PG_CONN

def request(flow: http.HTTPFlow) -> None:
    if any(domain in flow.request.host for domain in AD_DOMAINS):
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ads.ad_requests (session_id, domain, method, url, headers, body_raw, body_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                flow.request.headers.get("X-Session-Id", "unknown"),
                flow.request.host,
                flow.request.method,
                flow.request.url,
                json.dumps(dict(flow.request.headers)),
                flow.request.raw_content,
                None
            )
        )
        flow.request.id = cur.fetchone()[0]
        cur.close()

def response(flow: http.HTTPFlow) -> None:
    if any(domain in flow.request.host for domain in AD_DOMAINS):
        conn = get_pg_conn()
        cur = conn.cursor()
        has_nonce = b"nonce" in (flow.response.raw_content or b"")
        has_s2s = b"transaction_id" in (flow.response.raw_content or b"")
        has_sig = b"signature" in (flow.response.raw_content or b"")
        cur.execute(
            """
            INSERT INTO ads.ad_responses (request_id, status_code, headers, body_raw, body_json, has_nonce, has_s2s_token, has_signature)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                getattr(flow.request, "id", None),
                flow.response.status_code,
                json.dumps(dict(flow.response.headers)),
                flow.response.raw_content,
                None,
                has_nonce,
                has_s2s,
                has_sig
            )
        )
        cur.close()
