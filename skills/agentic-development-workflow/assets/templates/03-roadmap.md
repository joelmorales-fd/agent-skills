<!-- ADW-TEMPLATE: derive every step and risk from the verified investigation, then remove this marker -->
# Plan: [Ticket ID — Title]

**North Star:** [Observable outcome]
**Ticket:** [ID]
**Overall:** next

## Steps

| # | Step | File(s) | Done when | Status |
|---:|---|---|---|---|
| 1 | Write the repository-supported acceptance test | [test files] | Exact command produces RED for the missing behavior | next |
| 2 | Implement the smallest approved change | [implementation files] | The same proof is GREEN | next |
| 3 | Run the full affected suite | [module/suite] | No change-related failure remains | next |
| 4 | Run independent code review | change diff | All blocking findings are resolved | next |
| 5 | Complete local verification and evidence review | [selected topology] | Approved scenarios and final gates pass | next |

## Risks

| Risk | Caught by |
|---|---|
| [Concrete failure risk] | [Specific roadmap step and assertion] |
