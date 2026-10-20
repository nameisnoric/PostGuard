# Manual vision diagnostics

These modules open a physical camera, display OpenCV windows, or collect
interactive measurements. They are intentionally excluded from the automated
unit-test command.

Run a diagnostic from the `desktop` directory, for example:

```powershell
.\.venv\Scripts\python.exe -m tests.vision_manual.test_pose
```

Close the OpenCV window or follow the module's on-screen key instructions to
end a run.
