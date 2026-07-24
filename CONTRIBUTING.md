# Contributing

## Scope

This is an engineering repository for the Cat Door Project. Changes should improve reliability, diagnostics, maintainability or documented project capability.

## Branch and commit practice

The current repository can begin on a single main branch. Make small commits with a clear purpose, for example:

```text
Document ADS1115 wiring
Add raw sensor diagnostic output
Move PIR input to a non-conflicting GPIO
```

Do not commit generated clips, audio recordings, snapshots, logs, virtual environments, Python bytecode or credentials.

## Before changing working code

1. Record the current behavior and relevant log output.
2. Locate the exact source lines to be changed.
3. Make one functional change at a time.
4. Run the relevant hardware test.
5. Compile-check the Python files.
6. Update the documentation when wiring, thresholds, GPIO assignments or operating procedures change.

## Python conventions

- Use descriptive constant names for GPIOs, thresholds and timing values.
- Keep hardware initialization close to startup and cleanup explicit.
- Log state transitions rather than flooding identical samples.
- Distinguish sensor faults from valid occupied/clear states.
- Avoid broad exception handling unless the exception is logged with context.
- Do not silently change safety behavior.

## Legacy policy

Files under `legacy/` are retained to explain development history. Bug fixes and new features belong in `src/`, not in legacy copies.

## Credentials and private data

Never commit:

- GitHub personal access tokens;
- Wi-Fi passwords;
- private keys;
- browser/session secrets;
- recordings that should remain private;
- personal email addresses unless intentionally public.
