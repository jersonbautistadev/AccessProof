# Five-minute portfolio walkthrough

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

Open `reports/walkthrough/regression/report.html`. The same two bugs have been deliberately reintroduced. Four rows are marked `NEW FAILURE`. The CLI exits 1. `python -m scripts.ci_demo --mode vulnerable` demonstrates the corresponding blocking local CI command.

Show `.github/workflows/accessproof.yml`: it runs tests, invokes the CLI against the fixed fixture, and uploads sanitized reports even after failure. A GitHub branch rule must require the workflow check to block merging. A failing check alone does not configure branch protection.

## 5. State the limits clearly

“This is a configured regression tester. It does not discover unlisted endpoints or prove an application secure. I reproduced a missed leak where an unconfigured field escaped detection, and I treat authentication or fixture failures as inconclusive rather than successful denials.”

Show `docs/evaluation.md` and the corresponding test. Explain that four seeded unauthorized-access cases and a twelve-case valid matrix are a small fixture experiment, not a broad security benchmark.
