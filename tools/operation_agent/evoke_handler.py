from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os
import httpx
import logging

app = FastAPI(title="Operation Agent Evoke Handler")

logging.basicConfig(
    filename="operation_agent_audit.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


class EvokePayload(BaseModel):
    repository: str
    workflow: str
    run_id: str
    branch: str | None = None
    sha: str | None = None
    chat_session: str | None = None
    responsible_agents: list[str] | None = None


def _env(name: str) -> str | None:
    return os.environ.get(name)


@app.post("/evoke")
async def evoke(payload: EvokePayload, authorization: str | None = Header(None)):
    # Accept either OP_AGENT_SHARED_SECRET or OP_AGENT_TOKEN for compatibility
    secret = _env("OP_AGENT_SHARED_SECRET") or _env("OP_AGENT_TOKEN")
    if secret and authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="invalid auth token")

    dev_endpoint = _env("DEV_AGENT_ENDPOINT")
    test_endpoint = _env("TEST_AGENT_ENDPOINT")
    training_endpoint = _env("TRAINING_AGENT_ENDPOINT")

    if not dev_endpoint or not test_endpoint:
        raise HTTPException(
            status_code=500,
            detail="DEV_AGENT_ENDPOINT or TEST_AGENT_ENDPOINT not configured",
        )

    # Orchestrate: invoke dev agent then tester agent with same chat_session
    results = {"invocations": {}}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Invoke developer agent
        try:
            r = await client.post(
                f"{dev_endpoint.rstrip('/')}/evoke",
                json={
                    "chat_session": payload.chat_session,
                    "context": {
                        "source": "operation_agent",
                        "workflow": payload.workflow,
                        "run_id": payload.run_id,
                    },
                },
            )
            results["invocations"]["dev_agent"] = {
                "status_code": r.status_code,
                "body": r.text,
            }
        except Exception as e:
            results["invocations"]["dev_agent"] = {"error": str(e)}

        # Invoke tester agent
        try:
            r = await client.post(
                f"{test_endpoint.rstrip('/')}/evoke",
                json={
                    "chat_session": payload.chat_session,
                    "context": {
                        "source": "operation_agent",
                        "workflow": payload.workflow,
                        "run_id": payload.run_id,
                    },
                },
            )
            results["invocations"]["test_agent"] = {
                "status_code": r.status_code,
                "body": r.text,
            }
        except Exception as e:
            results["invocations"]["test_agent"] = {"error": str(e)}

        # If responsible agents provided, request retraining/penalization
        if training_endpoint and payload.responsible_agents:
            try:
                r = await client.post(
                    f"{training_endpoint.rstrip('/')}/penalize_and_retrain",
                    json={
                        "agents": payload.responsible_agents,
                        "reason": f"Workflow failure {payload.workflow} run {payload.run_id}",
                        "origin": "operation_agent",
                    },
                )
                results["invocations"]["training_agent"] = {
                    "status_code": r.status_code,
                    "body": r.text,
                }
            except Exception as e:
                results["invocations"]["training_agent"] = {"error": str(e)}

    logging.info(
        "Evoke called: repo=%s workflow=%s run_id=%s branch=%s sha=%s chat=%s agents=%s",
        payload.repository,
        payload.workflow,
        payload.run_id,
        payload.branch,
        payload.sha,
        payload.chat_session,
        payload.responsible_agents,
    )

    return {"status": "ok", "details": results}


class PenalizePayload(BaseModel):
    agents: list[str]
    reason: str | None = None
    origin: str | None = None


@app.post("/penalize_and_retrain")
async def penalize_and_retrain(
    payload: PenalizePayload, authorization: str | None = Header(None)
):
    """Example endpoint that receives a list of agents to penalize and schedules retraining.
    This is a local example implementation to complete the flow; in production this would enqueue
    work in a training system or call a dedicated training service.
    """
    secret = _env("OP_AGENT_SHARED_SECRET") or _env("OP_AGENT_TOKEN")
    if secret and authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="invalid auth token")

    logging.info(
        "Penalize request: agents=%s reason=%s origin=%s",
        payload.agents,
        payload.reason,
        payload.origin,
    )

    # Here we simulate scheduling retraining by writing an audit entry.
    try:
        with open("operation_agent_training_queue.log", "a") as f:
            f.write(
                f"{payload.agents} | reason={payload.reason} | origin={payload.origin}\n"
            )
    except Exception:
        logging.exception("Failed to write training queue log")

    return {"status": "scheduled", "agents": payload.agents}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8503")))
