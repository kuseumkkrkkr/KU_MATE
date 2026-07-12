from itertools import cycle

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

app = FastAPI()

BASE_URL = "https://integrate.api.nvidia.com/v1"

API_KEYS = [
    "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", 1
    "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", 2
]

key_cycle = cycle(range(len(API_KEYS)))


@app.api_route(
    "/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(path: str, request: Request):
    print(f"{request.method} /v1/{path}")

    body = await request.body()

    start = next(key_cycle)

    async with httpx.AsyncClient(timeout=None) as client:
        last = None

        for n in range(len(API_KEYS)):
            idx = (start + n) % len(API_KEYS)

            headers = {
                k: v
                for k, v in request.headers.items()
                if k.lower()
                not in (
                    "host",
                    "authorization",
                    "content-length",
                    "connection",
                )
            }

            headers["Authorization"] = f"Bearer {API_KEYS[idx]}"

            url = f"{BASE_URL}/{path}"

            req = client.build_request(
                request.method,
                url,
                params=request.query_params,
                headers=headers,
                content=body,
            )

            stream = await client.send(req, stream=True)

            if stream.status_code in (401, 403, 429):
                print(f"Key {idx+1} -> {stream.status_code}")
                last = stream
                await stream.aclose()
                continue

            response_headers = {
                k: v
                for k, v in stream.headers.items()
                if k.lower()
                not in (
                    "content-length",
                    "content-encoding",
                    "transfer-encoding",
                    "connection",
                )
            }

            content_type = stream.headers.get("content-type", "")

            if content_type.startswith("text/event-stream"):

                async def iterator():
                    async for chunk in stream.aiter_bytes():
                        yield chunk
                    await stream.aclose()

                return StreamingResponse(
                    iterator(),
                    status_code=stream.status_code,
                    headers=response_headers,
                    media_type="text/event-stream",
                )

            data = await stream.aread()
            await stream.aclose()

            return Response(
                content=data,
                status_code=stream.status_code,
                headers=response_headers,
            )

    if last is None:
        return Response("No API keys available", status_code=500)

    data = await last.aread()

    return Response(
        content=data,
        status_code=last.status_code,
    )