# NEWS
Формат (еженедельно):
- Дата
- Что нового
- Что применяем
- Риски/миграции
- Ссылки

## 2026-04-06
- Что нового:
  Codex chat закреплён как primary human frontdoor в тот же global managed contour; substantial work идёт через `/home/agent/bin/codex-frontdoor-preflight`, который вызывает тот же AI meta-launcher и оставляет frontdoor contract / manifest / trace
- Что нового:
  universal hardening подтвердил, что тот же contour покрывает readiness-only review, research/search routing, current-state lookup, clean rerun, broader eval, promotion preview, bootstrap и migration; совместимые topic-моды остались явными compatibility routes и больше не подавляют обычный intent-routing
- Что применяем:
  для новой managed работы из Codex используем Codex frontdoor + `codex-frontdoor-preflight`; `agent-exec` сохраняется как compatibility/automation entrypoint, а `agent-topic` остаётся только compatibility bootstrap alias
- Риски/миграции:
  `_shared` и `_runtime` остаются system roots, не topic roots; прямые component calls не запрещены железом, но считаются exception/compatibility mode; dynamic MCP attach и hard pre-exec Codex hook по-прежнему ограничены платформой
- Ссылки:
  `/home/agent/agents/docs/finalization/2026-04-06-ai-agent-contour-baseline-v1/REPO-AUDIT.md`
  `/home/agent/agents/docs/finalization/2026-04-06-ai-agent-contour-baseline-v1/FINAL-VERDICT.md`
