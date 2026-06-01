import asyncio
import io
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from database.database import Base
from database.models import Repository
from dotenv import load_dotenv
load_dotenv()
from services.extended_analytics import ExtendedAnalytics
from services.pdf_generator import generate_pdf_report
from config import DATABASE_URL

async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as db:
        repo_id = 1
        result = await db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()
        
        ext = ExtendedAnalytics(db)
        kpi = await ext.get_kpi_with_duration(repo_id, None, None, None, None, None)
        flow = await ext.get_monthly_flow_filtered(repo_id, 6)
        throughput = await ext.get_throughput_filtered(repo_id, 8)
        contrib_res = await ext.get_contributors_filtered(repo_id, page=1, limit=20)
        contributors = contrib_res.get("data", []) if contrib_res else []
        
        stale_res = await ext.get_stale_recommendations(repo_id, page=1, limit=15)
        stale = stale_res.get("data", []) if stale_res else []
        
        slow_res = await ext.get_slowest_merged_filtered(repo_id, page=1, limit=15)
        slowest = slow_res.get("data", []) if slow_res else []
        
        oldest_res = await ext.get_oldest_open_filtered(repo_id, page=1, limit=20)
        oldest = oldest_res.get("data", []) if oldest_res else []
        
        risk_res = await ext.get_pr_risk_panel(repo_id, page=1, limit=15)
        risks = risk_res.get("data", []) if risk_res else []
        
        try:
            pdf_bytes = generate_pdf_report(
                repo=repo,
                kpi=kpi,
                flow=flow,
                throughput=throughput,
                contributors=contributors,
                stale=stale,
                slowest=slowest,
                oldest=oldest,
                risks=risks,
            )
            print(f"Success! {len(pdf_bytes)} bytes generated.")
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
