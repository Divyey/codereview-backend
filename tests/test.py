# move to folder api/ and run backendd

# from fastapi import APIRouter, Request, Header, HTTPException
# import hmac
# import hashlib
# from ..core.config import settings

# router = APIRouter()

# @router.post("/test")
# async def test_signature(
#     request: Request,
#     x_hub_signature_256: str = Header(None)
# ):
#     body = await request.body()
#     secret = settings.GITHUB_WEBHOOK_SECRET
#     computed = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
#     print(f"Computed signature: {computed}")
#     print(f"Received signature: {x_hub_signature_256}")

#     if not x_hub_signature_256:
#         raise HTTPException(status_code=400, detail="No X-Hub-Signature-256 header sent.")

#     if hmac.compare_digest(computed, x_hub_signature_256):
#         return {"match": True, "computed": computed, "received": x_hub_signature_256}
#     else:
#         return {"match": False, "computed": computed, "received": x_hub_signature_256}

# In main.py
# from app.api.test import router as test_router
# app.include_router(test_router)