"""Verification script for task 2.1 - dependencies in BASE_SYSTEM_PROMPT."""
import importlib.util

spec = importlib.util.spec_from_file_location("prompt_builder", "lambda/prompt_builder.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

prompt = mod.BASE_SYSTEM_PROMPT

checks = [
    ('"dependencies"' in prompt, "dependencies field in required fields list"),
    ("A ticket B blocks ticket A when A cannot begin until B is finished" in prompt, "blocking relationship instruction"),
    ("Never include the ticket" in prompt, "self-exclusion instruction"),
    ('"dependencies": []' in prompt, "example with empty dependencies"),
    ('"dependencies": ["Set up database schema"]' in prompt, "example with non-empty dependencies"),
    ("exact titles of other tickets" in prompt, "exact titles instruction"),
    ("empty list []" in prompt, "empty list instruction"),
]

all_passed = True
for result, description in checks:
    status = "PASS" if result else "FAIL"
    if not result:
        all_passed = False
    print(f"  [{status}] {description}")

if all_passed:
    print("\nAll verifications passed!")
else:
    print("\nSome verifications FAILED!")
    exit(1)
