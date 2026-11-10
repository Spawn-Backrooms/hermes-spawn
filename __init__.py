"""SPAWN Backrooms native Hermes plugin. Registration has no network side effects."""
from pathlib import Path

from .commands import Commands
from .hooks import Hooks
from .jobs import Jobs
from .lease import LeaseKeeper
from .schemas import SCHEMAS
from .state import State
from .tools import Tools


def register(ctx):
    jobs = Jobs(state=State(ctx.state), config=ctx.get_config)
    hooks = Hooks(jobs, ctx)
    tools = Tools(jobs, hooks)
    keeper = LeaseKeeper(jobs)
    jobs.keeper = keeper
    for name, schema in SCHEMAS.items():
        ctx.register_tool(name=name, toolset="spawn-backrooms", schema=schema, handler=tools.handler(name))
    ctx.register_hook("pre_tool_call", hooks.pre_tool_call)
    ctx.register_hook("pre_llm_call", hooks.pre_llm_call)
    commands = Commands(jobs, tools)
    ctx.register_command("spawn", commands.slash, description="SPAWN access, assigned work and recorded earnings", args_hint="status|jobs|job <id>|earnings|connect")
    ctx.register_cli_command("spawn", "Inspect SPAWN access and assigned work", commands.setup_cli, commands.cli)
    ctx.register_skill("work-a-job", Path(__file__).parent / "skills" / "work-a-job" / "SKILL.md")
    ctx.on_unload(keeper.close)
