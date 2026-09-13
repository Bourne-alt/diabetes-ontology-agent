"""Safe model availability probe; prints no credentials or provider error bodies."""

from dmo.assessment.composer import ModelClient, ProviderError
from dmo.assessment.settings import ModelSettings


def main():
    client = ModelClient(ModelSettings.load())
    try:
        resolved = client.resolve()
        result = client.chat('Return JSON {"ok":true}.', {"purpose": "synthetic connectivity test"})
        print(
            {
                "requested_model": client.settings.model,
                "resolved_model": resolved,
                "ok": result == {"ok": True},
            }
        )
        return 0 if result == {"ok": True} else 1
    except ProviderError as exc:
        print({"ok": False, "reason": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
