Run the failure-first loop on component: $ARGUMENTS
1. Read docs/SAFETY_CONTRACT.md and the component's section in the build prompt.
2. Write a failing test for each failure mode you can think of, plus new ones.
3. Show the red run. Fix at root cause. Show green. Revert the fix once to prove the test catches it.
4. Append to docs/FAILURES.md. Re-run dev eval; report any change in false-confidence rate.