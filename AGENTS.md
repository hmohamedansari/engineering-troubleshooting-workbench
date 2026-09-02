# Working in this learning repository

This repository teaches boundaries in AI systems. Keep them visible.

- Prefer a small, clear function to an abstraction that hides the lesson.
- Keep deterministic rules, policy checks, tools, state and model adapters separate.
- Treat model output as a proposal until application code validates it.
- Do not add network calls, write-capable tools or a model dependency to the deterministic foundation.
- Keep every scenario synthetic and local.
- Run `pytest` after changing investigation logic.
- When suggesting a change, explain which component owns the new behaviour and how a learner can observe it.
