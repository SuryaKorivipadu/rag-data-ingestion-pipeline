# Engineering Guidelines

These guidelines apply to the entire repository.

## General principles

- Make the smallest focused change that solves the request.
- Preserve existing behavior and public interfaces unless a change is required.
- Follow the conventions already established in the surrounding code.
- Do not modify unrelated files or perform broad refactoring without a clear reason.
- Never commit passwords, API keys, tokens, connection strings with credentials, or other secrets.
- Keep local configuration in ignored `.env` files and commit only safe `.env.example` templates.

## Naming and structure

- Use descriptive names that communicate intent; avoid one-letter variables except for conventional short-lived indices.
- Python modules and functions use `snake_case`.
- Python classes use `PascalCase`.
- Constants use `UPPER_SNAKE_CASE`.
- Keep each service independently runnable with its own dependencies, entrypoint, tests, and documentation.
- Keep orchestration logic in Airflow DAGs and business logic in the appropriate FastAPI service.
- Do not duplicate workflow orchestration inside FastAPI applications.

## Python and FastAPI

- Add type annotations to public functions, task boundaries, request models, and response models where practical.
- Use Pydantic models for structured request and response data instead of unvalidated dictionaries.
- Keep route handlers thin; delegate document processing, database access, and external service calls to focused modules.
- Return appropriate HTTP status codes and stable, useful error details without exposing credentials, stack traces, or internal paths.
- Validate input at service boundaries, including file paths, identifiers, status values, and payload sizes.
- Use dependency injection for database connections and external clients when it improves testability.
- Make service operations idempotent where retries are possible.

## Error handling and logging

- Catch specific expected exceptions rather than using a bare or broad `except`.
- Log failures with operation context, identifiers, and safe diagnostic details.
- Do not log passwords, tokens, document contents, or sensitive personal data.
- Use appropriate log levels: `DEBUG` for diagnostic detail, `INFO` for normal lifecycle events, `WARNING` for recoverable problems, and `ERROR` or `EXCEPTION` for failures.
- Preserve the original exception when re-raising or translating an error.
- Fail clearly when required configuration is missing instead of silently using unsafe defaults.

## Database and ingestion state

- Use parameterized SQL for values; never interpolate untrusted values into SQL.
- Use structured SQL identifier handling when dynamic identifiers are unavoidable.
- Use transactions for related writes and make schema initialization or migrations repeatable where practical.
- Add constraints for invariants such as unique file hashes and valid lifecycle statuses.
- Track document identity using a stable identifier or content hash, not only a display filename.
- Design ingestion steps to tolerate Airflow retries without duplicate chunks, embeddings, or vector records.
- Keep Airflow metadata separate from application data tables.
- Prefer PostgreSQL for multi-service or production workloads; use SQLite only for local, low-concurrency development.

## Airflow

- Keep one clear DAG responsible for scheduling and task dependencies.
- Use retries, timeouts, and explicit failure behavior for external service calls.
- Pass small metadata references through XCom; store large documents, chunks, and embeddings in shared storage.
- Configure service URLs and credentials through environment variables or Airflow connections.
- Do not hard-code hostnames, ports, passwords, or secrets in DAG code.
- Make task boundaries observable and update document status consistently.
- Prevent concurrent runs from processing the same document unless concurrency is intentionally designed.

## Docker and configuration

- Pin or constrain dependency versions for reproducible builds.
- Use a suitable slim base image and avoid unnecessary build tools in runtime images.
- Run containers as a non-root user when practical.
- Keep health checks and startup commands explicit.
- Document required environment variables and provide safe example values.
- Ensure paths and service names work in the target environment, especially when Windows hosts access Linux containers.

## Testing and validation

- Add focused tests for new behavior, validation, error paths, and retry/idempotency behavior.
- Run the narrowest relevant test first after an edit.
- At minimum, run syntax or type checks for changed Python files.
- Validate API contracts at service boundaries.
- Do not weaken or delete tests merely to make a change pass.
- Report unavailable tools, skipped tests, and known residual risks clearly.

## Documentation

- Update the nearest README or configuration example when setup, commands, endpoints, or environment variables change.
- Document assumptions at integration boundaries.
- Keep comments concise and explain why non-obvious code exists, not what obvious code does.
