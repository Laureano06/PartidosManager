from fastapi import APIRouter

router = APIRouter()

@router.post("/admin/seed", tags=["Admin"])
async def seed_endpoint(reset: bool = False):
    from seed import seed
    await seed(reset=reset)
    return {"status": "ok"}

