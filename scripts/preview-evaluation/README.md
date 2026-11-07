# Exploratory code-preview evaluation

Development aid, not a benchmark or release gate. These simple tasks and their cases are public and were already used during development. A passing score neither proves general coding quality nor provides a held-out result. Use new, independently designed representative tasks before drawing quality conclusions.

The collector invokes the existing extension client and local runtime explicitly. It sends the task instruction, **not the fixed cases**, to the model. It creates a new file with mode 0600 where supported, without executing it or overwriting an existing file; this is not a cross-platform ACL guarantee. A failed collection can leave an empty or partially written file: it is not a preview and should be removed manually. It does not test the VS Code UI, assess model authenticity, or enforce a compute cap. The pairing and output paths must be trusted. Treat output as untrusted.

With a compatible runtime and approved model already running, select a fixed task (`ipv4`, `method`, or `bytes`) and use the existing runtime pairing file. Never put the token value itself on the command line or in logs:

```sh
node scripts/preview-evaluation/collect.cjs bytes /path/to/pairing-file /path/to/new-output.js
```

**Scoring executes the selected JavaScript with all privileges of the scoring process. The scorer is not a sandbox.** Do not run it on generated code until a human has inspected the entire file and explicitly approved execution. Use a disposable, isolated environment without network access, credentials or sensitive files, with appropriate resource and time limits. Inspect both the code and the fixed cases; they can be incomplete. After isolation and review, the separate manual step is:

```sh
node scripts/preview-evaluation/manual-score.cjs --i-reviewed-this-code bytes /path/to/reviewed-output.js
```

Never pass unreviewed or untrusted code to the scorer. It can read, modify or exfiltrate data and can hang or spawn processes. The acknowledgement flag is only a friction step, not a security boundary. Check the exit code as well as output: a failed import leaves every case unrun. Do not equate a successful preview with a correct solution.
