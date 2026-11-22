# Portfolio walkthroughs

## Two-minute version (live viewer)

Use https://accessproof-iota.vercel.app. Nothing needs to run locally.

**0:00 Problem (20 s).** "The most common serious API bug is a missing ownership or role check: a normal user reads someone else's record or calls an admin endpoint. Normal tests miss it, because the legitimate request still works. AccessProof checks every identity against every resource, using an explicit permission policy, and blocks CI when access doesn't match."

**0:20 The map (30 s).** Open the **Regression** sample. "Each resource is a room, each test identity a keycard, and each check a door. Green doors behaved. These four orange doors opened for the wrong keycard: Alice and Bob reading each other's records, and both reaching the admin audit log. They're marked *new* because they passed against the fixed baseline. The gate is blocked, and that's the same verdict that set the CLI's exit code."

**0:50 The evidence (30 s).** Click the **bob-record / alice** door. "Before trusting any result, AccessProof verified Alice's identity and confirmed Bob can read his own record. Then Alice's request came back 200, 82 bytes, and contained the protected field `/private_note`. The report records *that* the field was present, never its value. Reports are built from an allowlist, and a JSON Schema enforces it."

**1:20 One decision (25 s).** "A 403 doesn't count as a pass unless the prerequisites worked. An expired token or a missing record makes the check *inconclusive*, and inconclusive blocks CI too. A security gate that passes when it can't see is worse than none."

**1:45 Limits and next (15 s).** "It only tests what the policy declares, and there's a test that reproduces a leak it misses on purpose. Next is collection endpoints, where many real leaks appear."

Have a backup ready: a screenshot of the Regression sample with the panel open, `docs/images/viewer-regression.png`, in case the network fails.

---

## Five-minute version (local CLI)

## 1. State the problem

“A backend change can accidentally let a normal user read another user's private record or use an admin-only endpoint. I wanted a repeatable local and CI check against explicit permission rules.”

Show the matrix in the README and `configs/demo.toml`. There are two ordinary identities, one administrator, and one anonymous identity. All data and bearer credentials are synthetic. The target is a literal loopback address.

## 2. Detect and explain a failure

Run `python -m scripts.walkthrough`. The first stage uses the vulnerable demo. Open `reports/walkthrough/vulnerable/report.html`.

Choose `permission:bob-record:alice`:

- Expected permission: deny.
- Alice's subject and role were verified before testing.
- Bob's own successful read confirmed the resource and response contract.
- Alice's request returned HTTP 200 and included `/private_note`.
- Outcome: failed, `protected_fields_exposed`; CLI exited 1.

The evidence records that the field was present, without retaining the private value. This is an ownership enforcement failure, commonly discussed as BOLA/IDOR. Then show Alice's access to `admin-audit`, which illustrates missing function authorization.

## 3. Explain the correction

Open `accessproof/demo.py` and find the two enforcement points. In fixed mode, a record is returned only if the authenticated subject owns it or has the administrator role. The audit endpoint requires the administrator role. Both decisions happen on the server before serializing protected data.

For a hands-on version, use the two-terminal commands in the README. Stop `--mode vulnerable`, start `--mode fixed`, and rerun against the prior report. Switching modes selects the included corrected implementation; it does not edit the permission policy to hide the failures.

## 4. Show the corrected run and regression protection

Open `reports/walkthrough/fixed/report.html`. The fingerprint is unchanged because the intended policy did not change. All 12 permission cases and six prerequisites pass. The comparison records four resolved failures.

Open `reports/walkthrough/regression/report.html`, or drop `reports/walkthrough/regression/report.json` onto the [report viewer](https://accessproof-iota.vercel.app) for the access-plan view. The same two bugs have been deliberately reintroduced. Four rows are marked `NEW FAILURE`. The CLI exits 1. `python -m scripts.ci_demo --mode vulnerable` demonstrates the corresponding blocking local CI command.

Show `.github/workflows/accessproof.yml`: it runs tests, invokes the CLI against the fixed fixture, and uploads sanitized reports even after failure. This repository's ruleset requires the workflow's checks before anything merges into `main`. A failing check alone does not configure branch protection, so that ruleset is what makes the gate block.

## 5. State the limits clearly

“This is a configured regression tester. It does not discover unlisted endpoints or prove an application secure. I reproduced a missed leak where an unconfigured field escaped detection, and I treat authentication or fixture failures as inconclusive rather than successful denials.”

Show `docs/evaluation.md` and the corresponding test. Explain that four seeded unauthorized-access cases and a twelve-case valid matrix are a small fixture experiment, not a broad security benchmark.
