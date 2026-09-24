---
name: "Pytest Test Suite Generator"
description: "Automatically generates comprehensive, isolated unit tests using Pytest and mock fixtures for any Python file."
triggers: ["/generate-tests", "user asks to test a file", "test coverage is failing"]
---

# Operational Instructions

When this skill is activated, you must execute the following deterministic workflow sequence:

## Step 1: Input Analysis
1. Identify the target Python module to be tested.
2. Scan the file for external network calls, database sessions, or file I/O operations.

## Step 2: Context Isolation & Mocking
- If database models or sessions are detected, write a clean Pytest fixture utilizing an in-memory SQLite database or mock session.
- If HTTP/API calls are present, use `pytest-mock` or `responses` to completely isolate the execution from the network.

## Step 3: Test Generation Strategy
Generate a test suite containing:
- **Happy Path Tests:** 2-3 test cases verifying expected inputs deliver expected outputs.
- **Edge Case Tests:** Test cases handling empty payloads, extreme boundary integers, and `None` values.
- **Exception/Error Tests:** Force code paths to raise explicit errors to verify that error-handling logic works.

## Step 4: Output Execution Layout
Save the generated file inside the `tests/` directory mirroring the source file structure. 
- Example input: `app/services/auth.py`
- Example output: `tests/services/test_auth.py`

## Enforcement Rule
Do not output raw Markdown text directly to the user conversation. Write the test suite directly into the target destination file and report back with a 2-line summary of executed test counts.
