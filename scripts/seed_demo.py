#!/usr/bin/env python3
"""
Seed script for Telex demo repositories, breaking changes, patches, and incidents.

Creates 3 realistic demo repositories:
  1. acme/web-app: Next.js repo depending on openai@3.3.0 -> 4.0.0 (Open PR #142)
  2. acme/data-pipeline: Python repo depending on pydantic@1.10.8 -> 2.0.0 (Merged PR #88)
  3. acme/api-gateway: Express repo depending on axios@0.27.2 -> 1.6.0 (Open PR #57, semantic risk)

Usage:
  python scripts/seed_demo.py
  python scripts/seed_demo.py --clean
  python scripts/seed_demo.py --sqlite
"""

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add apps/api to sys.path so models and config can be imported
API_DIR = Path(__file__).resolve().parent.parent / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from db.models import (
    Base,
    CodeUsage,
    DetectedChange,
    IncidentEvent,
    Installation,
    Package,
    PackageVersion,
    Patch,
    PullRequest,
    Repo,
    User,
    ValidationRun,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def get_demo_engine(sqlite_mode: bool = False, custom_url: str | None = None):
    if custom_url:
        db_url = custom_url
    elif sqlite_mode:
        db_url = f"sqlite+aiosqlite:///{API_DIR / 'telex_demo.db'}"
    else:
        # Default to environment variable or fallback to local SQLite for zero-Docker
        env_url = os.getenv("DATABASE_URL")
        if env_url and "postgresql" in env_url:
            db_url = env_url
        else:
            db_url = f"sqlite+aiosqlite:///{API_DIR / 'telex_demo.db'}"

    engine_kwargs = {"echo": False}
    if "sqlite" in db_url:
        from sqlalchemy.pool import StaticPool

        engine_kwargs["connect_args"] = {"check_same_thread": False}
        engine_kwargs["poolclass"] = StaticPool
    else:
        engine_kwargs.update(
            {
                "pool_size": 5,
                "max_overflow": 10,
                "pool_pre_ping": True,
            }
        )

    return create_async_engine(db_url, **engine_kwargs), db_url


async def seed_demo_data(engine, clean: bool = False) -> None:
    # 1. Ensure all tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        if clean:
            print("Wiping existing demo data...")
            await session.execute(delete(IncidentEvent))
            await session.execute(delete(PullRequest))
            await session.execute(delete(ValidationRun))
            await session.execute(delete(Patch))
            await session.execute(delete(CodeUsage))
            await session.execute(delete(DetectedChange))
            await session.execute(delete(PackageVersion))
            await session.execute(delete(Package))
            await session.execute(delete(Repo))
            await session.execute(delete(Installation))
            await session.execute(delete(User))
            await session.commit()
            print("Database cleaned.")

        # 2. Check if demo user already exists
        existing_user = (
            await session.execute(select(User).where(User.github_login == "demo-user"))
        ).scalar_one_or_none()
        if existing_user and not clean:
            print("Demo data already present. Use --clean to wipe and re-seed.")
            return

        print("Seeding demo user and installation...")
        demo_user = User(
            id=uuid.uuid4(),
            github_id=987123,
            github_login="demo-user",
            email="demo@acme.corp",
            avatar_url="https://avatars.githubusercontent.com/u/987123?v=4",
        )
        session.add(demo_user)

        demo_inst = Installation(
            id=uuid.uuid4(),
            github_installation_id=884422,
            account_login="acme",
            account_type="Organization",
            installed_by=demo_user.id,
        )
        session.add(demo_inst)
        await session.flush()

        now = datetime.now(timezone.utc)

        # ── DEMO REPO 1: acme/web-app (openai@3.3.0 -> 4.0.0) ──────────────────
        print("Seeding acme/web-app (Next.js + OpenAI migration)...")
        repo_web = Repo(
            id=uuid.uuid4(),
            installation_id=demo_inst.id,
            github_repo_id=1001,
            full_name="acme/web-app",
            default_branch="main",
            is_active=True,
            requires_tests=True,
            requires_typecheck=True,
        )
        session.add(repo_web)

        pkg_openai = Package(id=uuid.uuid4(), ecosystem="npm", name="openai")
        session.add(pkg_openai)
        pv_openai_old = PackageVersion(
            id=uuid.uuid4(), package_id=pkg_openai.id, version="3.3.0"
        )
        pv_openai_new = PackageVersion(
            id=uuid.uuid4(), package_id=pkg_openai.id, version="4.0.0"
        )
        session.add_all([pv_openai_old, pv_openai_new])

        dc_openai = DetectedChange(
            id=uuid.uuid4(),
            package_version_id=pv_openai_new.id,
            source="npm_registry",
            change_type="signature_change",
            symbol_old="createCompletion",
            symbol_new="chat.completions.create",
            description="The legacy createCompletion endpoint has been replaced by chat.completions.create with a new options shape.",
            confidence=0.96,
        )
        session.add(dc_openai)
        await session.flush()

        cu_openai = CodeUsage(
            id=uuid.uuid4(),
            repo_id=repo_web.id,
            detected_change_id=dc_openai.id,
            file_path="src/pages/api/ai.ts",
            line_start=18,
            line_end=22,
            snippet="""const response = await openai.createCompletion({
    model: "text-davinci-003",
    prompt: query,
    max_tokens: 500,
});""",
            status="patched",
        )
        session.add(cu_openai)

        diff_openai = """--- a/src/pages/api/ai.ts
+++ b/src/pages/api/ai.ts
@@ -18,5 +18,5 @@
-const response = await openai.createCompletion({
-    model: "text-davinci-003",
-    prompt: query,
-    max_tokens: 500,
-});
+const response = await openai.chat.completions.create({
+    model: "gpt-4",
+    messages: [{ role: "user", content: query }],
+    max_tokens: 500,
+});"""

        patch_openai = Patch(
            id=uuid.uuid4(),
            code_usage_id=cu_openai.id,
            diff=diff_openai,
            llm_provider="gemini",
            llm_model="gemini-2.5-flash",
            prompt_version="v1",
            verified=True,
        )
        session.add(patch_openai)
        await session.flush()

        vr_openai = ValidationRun(
            id=uuid.uuid4(),
            patch_id=patch_openai.id,
            verification_mode="full",
            applies_cleanly=True,
            parses=True,
            typechecks=True,
            tests_pass=True,
            scope_ok=True,
            log="[base_sha:a1b2c3d4e5f6] [commit_sha:f6e5d4c3b2a1]\nTypeScript typecheck passed.\nJest test suite (14 suites, 82 tests) passed cleanly.",
        )
        session.add(vr_openai)

        pr_openai = PullRequest(
            id=uuid.uuid4(),
            repo_id=repo_web.id,
            package_version_id=pv_openai_new.id,
            github_pr_number=142,
            github_pr_url="https://github.com/acme/web-app/pull/142",
            status="open",
            patch_ids=[patch_openai.id],
            opened_at=now,
        )
        session.add(pr_openai)

        events_openai = [
            ("change_detected", {"package": "openai", "version": "4.0.0"}),
            ("usage_found", {"file": "src/pages/api/ai.ts", "line": 18}),
            ("patch_generated", {"model": "gemini-2.5-flash"}),
            ("validation_passed", {"mode": "full", "tests": True, "types": True}),
            ("pr_opened", {"github_pr_number": 142, "github_pr_url": pr_openai.github_pr_url}),
        ]
        for etype, payload in events_openai:
            session.add(
                IncidentEvent(
                    id=uuid.uuid4(),
                    repo_id=repo_web.id,
                    event_type=etype,
                    code_usage_id=cu_openai.id,
                    detected_change_id=dc_openai.id,
                    payload=payload,
                )
            )

        # ── DEMO REPO 2: acme/data-pipeline (pydantic@1.10.8 -> 2.0.0) ─────────
        print("Seeding acme/data-pipeline (Python + Pydantic v2 migration)...")
        repo_data = Repo(
            id=uuid.uuid4(),
            installation_id=demo_inst.id,
            github_repo_id=1002,
            full_name="acme/data-pipeline",
            default_branch="main",
            is_active=True,
            requires_tests=True,
            requires_typecheck=True,
        )
        session.add(repo_data)

        pkg_pydantic = Package(id=uuid.uuid4(), ecosystem="pypi", name="pydantic")
        session.add(pkg_pydantic)
        pv_pydantic_old = PackageVersion(
            id=uuid.uuid4(), package_id=pkg_pydantic.id, version="1.10.8"
        )
        pv_pydantic_new = PackageVersion(
            id=uuid.uuid4(), package_id=pkg_pydantic.id, version="2.0.0"
        )
        session.add_all([pv_pydantic_old, pv_pydantic_new])

        dc_pydantic = DetectedChange(
            id=uuid.uuid4(),
            package_version_id=pv_pydantic_new.id,
            source="internal_runtime",
            change_type="renamed",
            symbol_old="dict",
            symbol_new="model_dump",
            description="BaseModel.dict() is deprecated and replaced with BaseModel.model_dump().",
            confidence=0.98,
        )
        session.add(dc_pydantic)
        await session.flush()

        cu_pydantic = CodeUsage(
            id=uuid.uuid4(),
            repo_id=repo_data.id,
            detected_change_id=dc_pydantic.id,
            file_path="pipeline/transformers/user_cleaner.py",
            line_start=34,
            line_end=35,
            snippet="record_dict = user_model.dict(exclude_unset=True)",
            status="patched",
        )
        session.add(cu_pydantic)

        diff_pydantic = """--- a/pipeline/transformers/user_cleaner.py
+++ b/pipeline/transformers/user_cleaner.py
@@ -34,2 +34,2 @@
-record_dict = user_model.dict(exclude_unset=True)
+record_dict = user_model.model_dump(exclude_unset=True)
"""

        patch_pydantic = Patch(
            id=uuid.uuid4(),
            code_usage_id=cu_pydantic.id,
            diff=diff_pydantic,
            llm_provider="gemini",
            llm_model="gemini-2.5-flash",
            prompt_version="v1",
            verified=True,
        )
        session.add(patch_pydantic)
        await session.flush()

        vr_pydantic = ValidationRun(
            id=uuid.uuid4(),
            patch_id=patch_pydantic.id,
            verification_mode="full",
            applies_cleanly=True,
            parses=True,
            typechecks=True,
            tests_pass=True,
            scope_ok=True,
            log="[base_sha:b2c3d4e5f6a1] [commit_sha:a1f6e5d4c3b2]\npytest 7.4.0: 42 passed in 1.84s.\nmypy: Success: no issues found in 1 source file.",
        )
        session.add(vr_pydantic)

        pr_pydantic = PullRequest(
            id=uuid.uuid4(),
            repo_id=repo_data.id,
            package_version_id=pv_pydantic_new.id,
            github_pr_number=88,
            github_pr_url="https://github.com/acme/data-pipeline/pull/88",
            status="merged",
            merged=True,
            merged_at=now,
            patch_ids=[patch_pydantic.id],
            opened_at=now,
        )
        session.add(pr_pydantic)

        events_pydantic = [
            ("change_detected", {"package": "pydantic", "version": "2.0.0"}),
            ("usage_found", {"file": "pipeline/transformers/user_cleaner.py", "line": 34}),
            ("patch_generated", {"model": "gemini-2.5-flash"}),
            ("validation_passed", {"mode": "full", "tests": True, "types": True}),
            ("pr_opened", {"github_pr_number": 88, "github_pr_url": pr_pydantic.github_pr_url}),
            ("pr_merged", {"github_pr_number": 88}),
        ]
        for etype, payload in events_pydantic:
            session.add(
                IncidentEvent(
                    id=uuid.uuid4(),
                    repo_id=repo_data.id,
                    event_type=etype,
                    code_usage_id=cu_pydantic.id,
                    detected_change_id=dc_pydantic.id,
                    payload=payload,
                )
            )

        # ── DEMO REPO 3: acme/api-gateway (axios@0.27.2 -> 1.6.0) ──────────────
        print("Seeding acme/api-gateway (Express + Axios migration)...")
        repo_gateway = Repo(
            id=uuid.uuid4(),
            installation_id=demo_inst.id,
            github_repo_id=1003,
            full_name="acme/api-gateway",
            default_branch="main",
            is_active=True,
            requires_tests=True,
            requires_typecheck=False,
        )
        session.add(repo_gateway)

        pkg_axios = Package(id=uuid.uuid4(), ecosystem="npm", name="axios")
        session.add(pkg_axios)
        pv_axios_old = PackageVersion(
            id=uuid.uuid4(), package_id=pkg_axios.id, version="0.27.2"
        )
        pv_axios_new = PackageVersion(
            id=uuid.uuid4(), package_id=pkg_axios.id, version="1.6.0"
        )
        session.add_all([pv_axios_old, pv_axios_new])

        dc_axios = DetectedChange(
            id=uuid.uuid4(),
            package_version_id=pv_axios_new.id,
            source="npm_registry",
            change_type="behavior_change",
            symbol_old="transformResponse",
            symbol_new="transformResponse",
            description="Axios v1.x changed transformResponse signature to receive raw header object instead of parsed lookup.",
            confidence=0.82,
        )
        session.add(dc_axios)
        await session.flush()

        cu_axios = CodeUsage(
            id=uuid.uuid4(),
            repo_id=repo_gateway.id,
            detected_change_id=dc_axios.id,
            file_path="middleware/proxy.js",
            line_start=12,
            line_end=15,
            snippet="""const proxy = axios.create({
    transformResponse: [data => JSON.parse(data)],
});""",
            status="patched",
        )
        session.add(cu_axios)

        diff_axios = """--- a/middleware/proxy.js
+++ b/middleware/proxy.js
@@ -12,4 +12,4 @@
 const proxy = axios.create({
-    transformResponse: [data => JSON.parse(data)],
+    transformResponse: [(data, headers) => (typeof data === 'string' ? JSON.parse(data) : data)],
 });"""

        patch_axios = Patch(
            id=uuid.uuid4(),
            code_usage_id=cu_axios.id,
            diff=diff_axios,
            llm_provider="gemini",
            llm_model="gemini-2.5-flash",
            prompt_version="v1",
            verified=True,
        )
        session.add(patch_axios)
        await session.flush()

        vr_axios = ValidationRun(
            id=uuid.uuid4(),
            patch_id=patch_axios.id,
            verification_mode="full",
            applies_cleanly=True,
            parses=True,
            typechecks=None,
            tests_pass=True,
            scope_ok=True,
            log="[base_sha:c3d4e5f6a1b2] [commit_sha:d4c3b2a1f6e5]\nMocha test suite (26 tests) passed cleanly.",
        )
        session.add(vr_axios)

        pr_axios = PullRequest(
            id=uuid.uuid4(),
            repo_id=repo_gateway.id,
            package_version_id=pv_axios_new.id,
            github_pr_number=57,
            github_pr_url="https://github.com/acme/api-gateway/pull/57",
            status="open",
            patch_ids=[patch_axios.id],
            opened_at=now,
        )
        session.add(pr_axios)

        events_axios = [
            ("change_detected", {"package": "axios", "version": "1.6.0"}),
            ("usage_found", {"file": "middleware/proxy.js", "line": 12}),
            ("patch_generated", {"model": "gemini-2.5-flash"}),
            ("validation_passed", {"mode": "full", "tests": True}),
            ("pr_opened", {"github_pr_number": 57, "github_pr_url": pr_axios.github_pr_url}),
        ]
        for etype, payload in events_axios:
            session.add(
                IncidentEvent(
                    id=uuid.uuid4(),
                    repo_id=repo_gateway.id,
                    event_type=etype,
                    code_usage_id=cu_axios.id,
                    detected_change_id=dc_axios.id,
                    payload=payload,
                )
            )

        await session.commit()
        print("\nDemo data seeded successfully!")
        print("Summary of Seeded Data:")
        print("  - User: demo-user (Organization: acme)")
        print("  - Repositories: 3 (acme/web-app, acme/data-pipeline, acme/api-gateway)")
        print("  - Breaking Changes: 3 detected (OpenAI, Pydantic, Axios)")
        print("  - Verified Patches: 3 generated with full CI validation gates")
        print("  - Pull Requests: 2 open (#142, #57), 1 merged (#88)")
        print("  - Incident Events: 16 lifecycle event records")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Telex database with realistic demo repositories.")
    parser.add_argument("--clean", action="store_true", help="Wipe existing demo data before seeding")
    parser.add_argument("--sqlite", action="store_true", help="Use local SQLite database (zero-Docker)")
    parser.add_argument("--database-url", default=None, help="Custom database connection string")
    args = parser.parse_args()

    engine, db_url = get_demo_engine(sqlite_mode=args.sqlite, custom_url=args.database_url)
    print(f"Connecting to database: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    asyncio.run(seed_demo_data(engine, clean=args.clean))


if __name__ == "__main__":
    main()
